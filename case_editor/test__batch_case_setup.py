from pathlib import Path
import tempfile
import unittest
import numpy as np
from case_editor.batch_case_setup import (
    batch_preview_payload,
    create_batch_cases,
    create_grouped_cases,
    grouped_preview_payload,
    plan_grouped_variants,
    parse_body_groups,
    parse_offsets,
)
from case_editor.run_batch_console import BATCH_API_VERSION
from geometry.unstructure_surface.surface import SurfaceBody, read_surface, write_surface


class BatchCaseSetupTests(unittest.TestCase):
    def test_batch_api_version_identifies_point_cloud_schema(self):
        self.assertEqual(BATCH_API_VERSION, "position-names-v3")

    def test_body_range_moves_as_one_rigid_group(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); source = root / "source"; source.mkdir()
            bodies = [SurfaceBody(np.array([[1,i*10.,0.,0.],[2,i*10.+1,0.,0.],[3,i*10.,1.,0.]]), np.array([[1,1,2,3]])) for i in range(4)]
            write_surface(source / "unstruc_surface_in.dat", bodies)
            groups = parse_body_groups([{"body_ids":"2-4", "x":"0", "y":"0.1,0.2", "z":"0"}], 4)
            variants = create_grouped_cases(source, root / "batch", groups, "fish")
            self.assertEqual([variant.name for variant in variants], ["fish_YP0p1", "fish_YP0p2"])
            first = read_surface(variants[0].case_dir / "unstruc_surface_in.dat")
            np.testing.assert_allclose(first[0].nodes, bodies[0].nodes)
            for body_id in (2, 3, 4):
                np.testing.assert_allclose(first[body_id - 1].nodes[:, 2], bodies[body_id - 1].nodes[:, 2] + 0.1)

    def test_group_axes_allow_single_value_broadcast(self):
        groups = parse_body_groups([{"body_ids":"2,3,4", "x":"1", "y":"0.1,0.2,0.3", "z":"-2"}], 4)
        self.assertEqual(groups[0].body_ids, (2, 3, 4))
        self.assertEqual(groups[0].x, (1.0,))

    def test_body_cannot_appear_in_two_groups(self):
        with self.assertRaisesRegex(ValueError, "more than one group"):
            parse_body_groups([{"body_ids":"2-4"}, {"body_ids":"4"}], 4)

    def test_position_suffix_uses_axis_sign_and_decimal(self):
        groups = parse_body_groups([{"body_ids":"2-4", "x":"0", "y":"0.4,-0.2", "z":"0"}], 4)
        variants = plan_grouped_variants("output", groups, "tunabot")
        self.assertEqual([variant.name for variant in variants], ["tunabot_YP0p4", "tunabot_YM0p2"])

    def test_multiple_groups_include_body_ids_in_suffix(self):
        groups = parse_body_groups([
            {"body_ids":"1", "x":"0.1,0.2", "y":"0", "z":"0"},
            {"body_ids":"2-4", "x":"0", "y":"0.4,0.5", "z":"0"},
        ], 4)
        variants = plan_grouped_variants("output", groups, "pair")
        self.assertEqual(variants[0].name, "pair_B1_XP0p1_B2-4_YP0p4")

    def test_copy_and_translate_only_selected_body(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); source = root / "source"; source.mkdir()
            body1 = SurfaceBody(np.array([[1,0.,0.,0.],[2,1.,0.,0.],[3,0.,1.,0.]]), np.array([[1,1,2,3]]))
            body2 = SurfaceBody(np.array([[1,5.,0.,0.],[2,6.,0.,0.],[3,5.,1.,0.]]), np.array([[1,1,2,3]]))
            write_surface(source / "unstruc_surface_in.dat", [body1, body2]); (source / "input.dat").write_text("keep me")
            variants = create_batch_cases(source, root / "batch", 1, "y", [0.1, 0.2])
            self.assertEqual([v.name for v in variants], ["move_y_0p1", "move_y_0p2"])
            moved = read_surface(variants[0].case_dir / "unstruc_surface_in.dat")
            np.testing.assert_allclose(moved[0].nodes[:,2], body1.nodes[:,2] + 0.1)
            np.testing.assert_allclose(moved[1].nodes, body2.nodes)
            self.assertEqual((variants[0].case_dir / "input.dat").read_text(), "keep me")
            np.testing.assert_allclose(read_surface(source / "unstruc_surface_in.dat")[0].nodes, body1.nodes)

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir); source = root / "source"; source.mkdir()
            body = SurfaceBody(np.array([[1,0.,0.,0.],[2,1.,0.,0.],[3,0.,1.,0.]]), np.array([[1,1,2,3]]))
            write_surface(source / "unstruc_surface_in.dat", [body])
            (root / "batch" / "move_x_0p1").mkdir(parents=True)
            with self.assertRaises(FileExistsError):
                create_batch_cases(source, root / "batch", 1, "x", [0.1])

    def test_parse_offsets_rejects_duplicates(self):
        with self.assertRaisesRegex(ValueError, "unique"):
            parse_offsets("0.1, 0.1")

    def test_preview_sends_static_body_once_and_only_points(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            body1 = SurfaceBody(np.array([[1,0.,0.,0.],[2,1.,0.,0.],[3,0.,1.,0.]]), np.array([[1,1,2,3]]))
            body2 = SurfaceBody(np.array([[1,5.,0.,0.],[2,6.,0.,0.],[3,5.,1.,0.]]), np.array([[1,1,2,3]]))
            write_surface(source / "unstruc_surface_in.dat", [body1, body2])
            result = batch_preview_payload(source, 1, "z", [0.1, 0.2])
            self.assertEqual(len(result["static_bodies"]), 1)
            self.assertEqual(len(result["variants"]), 2)
            self.assertNotIn("elements", result["variants"][0])
            np.testing.assert_allclose(np.asarray(result["variants"][0]["points"])[:,2], body1.points[:,2] + 0.1)

    def test_group_preview_sends_all_changed_bodies_per_case(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir)
            bodies = [SurfaceBody(np.array([[1,i,0.,0.],[2,i+1,0.,0.],[3,i,1.,0.]]), np.array([[1,1,2,3]])) for i in range(4)]
            write_surface(source / "unstruc_surface_in.dat", bodies)
            groups = parse_body_groups([{"body_ids":"2-4", "y":"0.1,0.2"}], 4)
            result = grouped_preview_payload(source, groups, "fish", source.parent / "out")
            self.assertEqual([body["body_id"] for body in result["static_bodies"]], [1])
            self.assertEqual([body["body_id"] for body in result["cases"][0]["bodies"]], [2, 3, 4])


if __name__ == "__main__":
    unittest.main()
