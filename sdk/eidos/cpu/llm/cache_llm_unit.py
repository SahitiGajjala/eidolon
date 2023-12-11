import hashlib
import json
from typing import List, Optional

from pydantic import Field
from pydantic import ValidationError

from eidos.agent_os import AgentOS
from eidos.cpu.call_context import CallContext
from eidos.cpu.llm.open_ai_llm_unit import OpenAIGPT
from eidos.cpu.llm_message import LLMMessage, AssistantMessage
from eidos.cpu.llm_unit import LLMUnit, LLMUnitConfig, LLMCallFunction
from eidos.memory.agent_memory import FileMemory
from eidos.memory.local_file_memory import LocalFileMemory
from eidos.system.reference_model import Specable, AnnotatedReference, Reference


# Assuming CallContext, LLMMessage, LLMCallFunction, AssistantMessage are defined elsewhere

class CacheLLMSpec(LLMUnitConfig):
    dir: str = Field(default="llm_cache", description="The directory to store the cache in.")
    llm: AnnotatedReference[LLMUnit, OpenAIGPT]
    file_memory_override: Optional[Reference[FileMemory, LocalFileMemory]] = None


class CacheLLM(LLMUnit, Specable[CacheLLMSpec]):
    dir: str
    memory: FileMemory

    def __init__(self, spec: CacheLLMSpec, **kwargs):
        super().__init__(spec, **kwargs)
        self.dir = spec.dir
        if self.spec.file_memory_override:
            self.memory = self.spec.file_memory_override.instantiate()
        else:
            self.memory = AgentOS.file_memory
        self.memory.mkdir(self.dir, exist_ok=True)
        self.llm = spec.llm.instantiate(processing_unit_locator=self.processing_unit_locator)

    async def execute_llm(self, call_context: CallContext, inMessages: List[LLMMessage], inTools: List[LLMCallFunction], output_format: dict) -> AssistantMessage:
        try:
            # Generate the hash
            combined_str = ''.join(message.model_dump_json() for message in inMessages) + \
                           ''.join(tool.model_dump_json() for tool in inTools) + \
                           json.dumps(output_format)

            hash_object = hashlib.sha256()
            hash_object.update(combined_str.encode())
            hash_hex = hash_object.hexdigest()

            file_name = f"{self.dir}/{hash_hex}.json"

            if self.memory.exists(file_name):
                contents = self.memory.read_file(file_name)
                return LLMMessage.from_dict(json.loads(contents.decode()))
            else:
                result = await self.llm.execute_llm(call_context, inMessages, inTools, output_format)
                self.memory.write_file(file_name, json.dumps(result.dict()).encode())
                return result
        except ValidationError as ve:
            # Handle Pydantic validation errors
            raise ValueError(f"Input validation error") from ve
        except json.JSONDecodeError:
            # Handle JSON errors
            raise ValueError("Error in JSON processing")
        except IOError as io_err:
            # Handle File IO errors
            raise IOError(f"File operation error") from io_err
        except Exception as e:
            # Handle other exceptions
            raise Exception(f"Unexpected error occurred") from e
