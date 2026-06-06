from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from case_editor.workflow import CaseBuildConfig, InputBuildConfig, MeshBuildConfig, SurfaceBuildConfig, build_case


def main() -> None:
    """Build one complete 2D cylinder case with editable parameters."""
    config = CaseBuildConfig(
        case_dir="example/generated_circle2d_case",
        surface=SurfaceBuildConfig(
            kind="circle",
            params={
                "radius": 0.25,
                "n": 96,
            },
            center=(19.2, 10.0, 0.0),
        ),
        mesh=MeshBuildConfig(
            nx=121,
            ny=81,
            nz=1,
            xout=24.0,
            yout=20.0,
            zout=0.0,
        ),
        input=InputBuildConfig(
            u=1.0,
            v=0.0,
            w=0.0,
            re=1000.0,
            dt=0.001,
        ),
    )

    case = build_case(config)
    print(case.report())


if __name__ == "__main__":
    main()
