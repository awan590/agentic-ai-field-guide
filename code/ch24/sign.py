"""Week zero: sign a folder's pilot criteria with Chapter 20's hash.

    python -m ch24.sign FOLDER SIGNER [SIGNER ...]

Writes FOLDER/signoff.json: who signed, and the SHA-256 of
FOLDER/criteria.json as it stands now. Sign once, in week 0, with
every signer in the room; gate 6 refuses criteria changed after it.
"""
import json
import sys
from pathlib import Path

from ch20.go_no_go import fingerprint


def sign(folder, signers):
    """Write signoff.json for the criteria in folder; return it."""
    folder = Path(folder)
    crit = json.loads((folder / "criteria.json").read_text())
    signoff = {"signed_in": "week 0", "signed_by": list(signers),
               "criteria_sha256": fingerprint(crit)}
    (folder / "signoff.json").write_text(json.dumps(signoff, indent=2)
                                         + "\n")
    return signoff


def main(argv):
    if len(argv) < 2:
        print("usage: python -m ch24.sign FOLDER SIGNER [SIGNER ...]")
        return 2
    signoff = sign(argv[0], argv[1:])
    print(f"signed by {len(argv) - 1}, criteria "
          f"{signoff['criteria_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
