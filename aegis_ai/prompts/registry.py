from dataclasses import dataclass
import hashlib
from pathlib import Path
import yaml

PROMPTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PromptArtifact:
    prompt_id: str
    version: str
    system_prompt: str
    sha256_short: str

    @property
    def prompt_version(self) -> str:
        return f"v{self.version}-{self.sha256_short}"


def load_prompt(name: str = "system2_deliberate") -> PromptArtifact:
    path = PROMPTS_DIR / f"{name}.yaml"
    raw_bytes = path.read_bytes()
    data = yaml.safe_load(raw_bytes.decode("utf-8"))
    sha_short = hashlib.sha256(raw_bytes).hexdigest()[:8]
    return PromptArtifact(
        prompt_id=str(data["id"]),
        version=str(data["version"]),
        system_prompt=str(data["system_prompt"]).strip(),
        sha256_short=sha_short,
    )
