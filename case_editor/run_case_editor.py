from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from case_editor.case_project import DEFAULT_TEMPLATE_CASE, CaseProject  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edit Picar case input/canonical/mesh/surface files.")
    parser.add_argument("--case-dir", type=Path, required=True, help="Target case directory.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Copy a small editable template case.")
    init.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE_CASE)
    init.add_argument("--include-large", action="store_true", help="Also copy fort.* files.")

    mesh = sub.add_parser("mesh", help="Generate xgrid/ygrid/zgrid and update input.dat counts/domain.")
    mesh.add_argument("--nx", type=int, required=True)
    mesh.add_argument("--ny", type=int, required=True)
    mesh.add_argument("--nz", type=int, required=True)
    mesh.add_argument("--xout", type=float, required=True)
    mesh.add_argument("--yout", type=float, required=True)
    mesh.add_argument("--zout", type=float, required=True)

    inp = sub.add_parser("input", help="Edit common input.dat values.")
    inp.add_argument("--u", type=float, default=None)
    inp.add_argument("--v", type=float, default=None)
    inp.add_argument("--w", type=float, default=None)
    inp.add_argument("--re", type=float, default=None)
    inp.add_argument("--dt", type=float, default=None)
    inp.add_argument("--ib-present", type=int, default=None)
    inp.add_argument("--body-type", type=int, default=None)
    inp.add_argument("--formulation", type=int, default=None)

    canon = sub.add_parser("canonical", help="Sync canonical_body_in.dat from unstruc_surface_in.dat.")
    canon.add_argument("--nbody-solid", type=int, default=None)
    canon.add_argument("--nbody-membrane", type=int, default=0)
    canon.add_argument("--motion-type", type=int, default=3)
    canon.add_argument("--zone-max", type=int, default=1)

    sub.add_parser("report", help="Print full case report and validation.")
    sub.add_parser("validate", help="Validate case consistency.")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project = CaseProject(args.case_dir)

    if args.command == "init":
        project.copy_template(args.template, include_large=args.include_large)
        print(project.report())

    elif args.command == "mesh":
        project.generate_mesh(args.nx, args.ny, args.nz, args.xout, args.yout, args.zout)
        print(project.report())

    elif args.command == "input":
        editor = project.input_editor()
        if args.u is not None or args.v is not None or args.w is not None:
            vals = editor.get_values_after("uinit")
            u = args.u if args.u is not None else float(vals[0])
            v = args.v if args.v is not None else float(vals[1])
            w = args.w if args.w is not None else float(vals[2])
            editor.set_initial_velocity(u, v, w)
        if args.re is not None or args.dt is not None:
            vals = editor.get_values_after("re,")
            re = args.re if args.re is not None else float(vals[0])
            dt = args.dt if args.dt is not None else float(vals[1])
            editor.set_re_dt(re, dt)
        if args.ib_present is not None or args.body_type is not None or args.formulation is not None:
            ib_vals = editor.get_values_after("internal_boundary_present")
            body_vals = editor.get_values_after("body_type")
            form_vals = editor.get_values_after("boundary_formulation")
            editor.set_internal_boundary(
                present=args.ib_present if args.ib_present is not None else int(ib_vals[0]),
                iblank_fast=int(ib_vals[1]) if len(ib_vals) > 1 else 0,
                body_type=args.body_type if args.body_type is not None else int(body_vals[0]),
                formulation=args.formulation if args.formulation is not None else int(form_vals[0]),
            )
        editor.write()
        print(project.report())

    elif args.command == "canonical":
        project.sync_canonical_from_surface(
            nbody_solid=args.nbody_solid,
            nbody_membrane=args.nbody_membrane,
            motion_type=args.motion_type,
            zone_max=args.zone_max,
        )
        print(project.report())

    elif args.command == "report":
        print(project.report())

    elif args.command == "validate":
        errors = project.validate()
        print("Case Validation")
        print("===============")
        print("Status: " + ("PASS" if not errors else "FAIL"))
        for error in errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()
