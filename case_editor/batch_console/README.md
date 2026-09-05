# Batch Case Setup

Launch this workspace separately from the main Picar Console:

```powershell
python -B batch_console.py path\to\source_case
```

Define one or more rigid body groups. A group accepts a body range such as `2-4`
or a list such as `2,3,4`; all bodies in the group receive the same X/Y/Z
translation for a case. Axis fields accept either one value (broadcast to every
case) or one comma-/space-separated value per case.

Case directories use the requested prefix plus a position suffix. For example,
prefix `tunabot` and Y offset `+0.4` produce `tunabot_YP0p4`; negative offsets
use `M`, such as `tunabot_YM0p2`. When multiple groups move, their body ids are
included to keep the name unambiguous.
Preview overlays the changed body from every variant as a sampled 3D point cloud
without writing files. Unchanged bodies are drawn only once; variants use an
automatic opacity gradient and can be hidden independently. The viewport shares
the main console's camera projection and ISO/Top/XY/XZ/YZ behavior. **Create Cases** copies the complete source case,
then changes only `unstruc_surface_in.dat` in each copy. Existing target case
directories are never overwritten.
