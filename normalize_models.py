import glob
import os

target_models = [
    'assets/models/docking-station.obj',
    'assets/models/empty-shelf.obj',
    'assets/models/occupied-shelf.obj',
    'assets/models/robot.obj',
    'assets/models/robot-box.obj',
]

for path in target_models:
    if not os.path.exists(path):
        continue
    
    verts = []
    lines = []
    with open(path, 'r') as f:
        for line in f:
            lines.append(line)
            if line.startswith('v '):
                p = line.strip().split()
                verts.append([float(p[1]), float(p[2]), float(p[3])])
    
    if not verts:
        continue
        
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    
    cx = (min(xs) + max(xs)) / 2.0
    min_y = min(ys)
    cz = (min(zs) + max(zs)) / 2.0

    print(f"Normalizing {path}: Center offset ({cx:.3f}, {min_y:.3f}, {cz:.3f})")

    # Tulis ulang vertex dengan menggeser origin ke center bottom (0, 0, 0)
    with open(path, 'w') as f:
        for line in lines:
            if line.startswith('v '):
                p = line.strip().split()
                x = float(p[1]) - cx
                y = float(p[2]) - min_y
                z = float(p[3]) - cz
                f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
            else:
                f.write(line)

print("Normalisasi selesai!")