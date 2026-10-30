// Builds the 3D room of a listing photo with three.js and saves it as binary glTF (.glb).
//
//   node scripts/room-builder.mjs <layout.json> [<layout.json> ...]
//
// Each layout (written by scripts/rooms-3d.py) describes the room seen in one photo: size,
// colours of walls and floor, furniture recognised in the photo, cabinets along the walls and
// windows. The room is drawn as a clean model (floor, three walls, furniture as objects), not
// with the photo as texture; the side facing the viewer is left open, like a doll's house.
// The .glb is written next to its layout (same name, .glb extension).
//
// Units are meters. In the layout x runs across the photo and z away from the camera; in
// three.js the room extends along -z.
import { readFileSync, writeFileSync } from "node:fs";
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";

// GLTFExporter reads Blobs with FileReader, which Node does not have.
globalThis.FileReader ??= class {
  readAsArrayBuffer(blob) {
    void blob.arrayBuffer().then((data) => {
      this.result = data;
      this.onloadend?.();
    });
  }
  readAsDataURL(blob) {
    void blob.arrayBuffer().then((data) => {
      this.result = `data:${blob.type};base64,${Buffer.from(data).toString("base64")}`;
      this.onloadend?.();
    });
  }
};

const WOOD = [0.55, 0.4, 0.27];
const DARK = [0.18, 0.18, 0.2];
const WHITE = [0.94, 0.94, 0.92];
const GLASS = [0.72, 0.84, 0.95];
const STEEL = [0.82, 0.83, 0.85];

/** A clean, lighter version of a colour sampled from the photo (photos are often in shadow). */
const tidy = (rgb, lift = 0.15) => rgb.map((c) => Math.max(0, Math.min(1, c + (1 - c) * lift)));
const clamp = (value, lo, hi) => Math.min(Math.max(value, lo), hi);

function buildRoom(layout) {
  const materials = new Map();
  const material = (rgb, roughness = 0.85) => {
    const key = `${rgb.map((c) => c.toFixed(2)).join()}/${roughness}`;
    if (!materials.has(key)) {
      materials.set(
        key,
        new THREE.MeshStandardMaterial({
          color: new THREE.Color().setRGB(rgb[0], rgb[1], rgb[2], THREE.SRGBColorSpace),
          roughness,
          metalness: 0,
        }),
      );
    }
    return materials.get(key);
  };
  const box = (group, w, h, d, x, y, z, rgb, roughness) => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material(rgb, roughness));
    mesh.position.set(x, y + h / 2, z);
    group.add(mesh);
  };
  const cylinder = (group, r, h, x, y, z, rgb) => {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(r, r * 0.85, h, 24), material(rgb));
    mesh.position.set(x, y + h / 2, z);
    group.add(mesh);
  };

  const { room } = layout;
  const scene = new THREE.Scene();

  // --- Shell: floor, back wall, side walls and skirting boards.
  const left = room.left - 0.3;
  const right = room.right + 0.3;
  const front = room.front;
  const back = room.back + 0.1;
  const width = right - left;
  const depth = back - front;
  const midX = (left + right) / 2;
  const midZ = -(front + back) / 2;
  const wall = tidy(room.wall, 0.35);
  const shell = new THREE.Group();
  shell.name = "stanza";
  box(shell, width + 0.2, 0.06, depth + 0.1, midX, -0.06, midZ, tidy(room.floor, 0.1), 0.7);
  box(shell, width + 0.2, room.height, 0.1, midX, 0, -back - 0.05, wall);
  box(shell, 0.1, room.height, depth, left - 0.05, 0, midZ, wall);
  box(shell, 0.1, room.height, depth, right + 0.05, 0, midZ, wall);
  box(shell, width, 0.08, 0.02, midX, 0, -back + 0.01, WHITE);
  box(shell, 0.02, 0.08, depth, left + 0.01, 0, midZ, WHITE);
  box(shell, 0.02, 0.08, depth, right - 0.01, 0, midZ, WHITE);
  scene.add(shell);

  // --- Cabinets and windows along the walls. Built facing +z, then turned onto their wall.
  for (const fixture of layout.fixtures) {
    const group = new THREE.Group();
    group.name = fixture.type === "cabinet" ? "mobile" : "finestra";
    const length = fixture.to - fixture.from;
    const middle = (fixture.from + fixture.to) / 2;
    if (fixture.type === "cabinet") {
      const colour = tidy(fixture.color, 0.15);
      box(group, length, fixture.height, fixture.depth, 0, 0, fixture.depth / 2, colour);
      // Low units (kitchen, chests of drawers) get a worktop.
      if (fixture.height < 1.2)
        box(
          group,
          length + 0.02,
          0.04,
          fixture.depth + 0.03,
          0,
          fixture.height,
          fixture.depth / 2 + 0.015,
          tidy(colour, -0.35),
          0.4,
        );
      const doors = Math.max(1, Math.round(length / 0.5));
      for (let i = 1; i < doors; i++) {
        const x = -length / 2 + (length / doors) * i;
        box(
          group,
          0.012,
          fixture.height - 0.1,
          0.01,
          x,
          0.05,
          fixture.depth + 0.005,
          tidy(colour, -0.3),
        );
      }
    } else {
      const height = fixture.top - fixture.bottom;
      box(group, length, height, 0.04, 0, fixture.bottom, 0.02, WHITE);
      box(group, length - 0.1, height - 0.1, 0.05, 0, fixture.bottom + 0.05, 0.02, GLASS, 0.1);
      box(group, 0.04, height - 0.1, 0.06, 0, fixture.bottom + 0.05, 0.02, WHITE);
    }
    if (fixture.wall === "back") group.position.set(middle, 0, -back);
    if (fixture.wall === "left") {
      group.rotation.y = Math.PI / 2;
      group.position.set(left, 0, -middle);
    }
    if (fixture.wall === "right") {
      group.rotation.y = -Math.PI / 2;
      group.position.set(right, 0, -middle);
    }
    scene.add(group);
  }

  // --- Furniture. Each builder draws the piece with its front at z = 0, extending to -z,
  // and returns its depth.
  const builders = {
    bed(g, it) {
      const w = clamp(it.width * 0.85, 0.9, 1.9);
      const length = 2.05;
      box(g, w + 0.08, 0.3, length, 0, 0, -length / 2, WOOD);
      box(g, w, 0.2, length - 0.1, 0, 0.3, -length / 2 + 0.02, tidy(it.color, 0.2));
      box(g, w + 0.08, 1.0, 0.08, 0, 0, -length + 0.04, WOOD);
      const pillows = w > 1.3 ? 2 : 1;
      for (let i = 0; i < pillows; i++) {
        const x = pillows === 1 ? 0 : (i - 0.5) * w * 0.5;
        box(g, Math.min(0.6, w / pillows - 0.1), 0.12, 0.35, x, 0.5, -length + 0.35, WHITE);
      }
      return length;
    },
    sofa(g, it) {
      const w = clamp(it.width, 1.4, 3);
      const colour = tidy(it.color, 0.1);
      box(g, w, 0.42, 0.9, 0, 0, -0.45, colour);
      box(g, w, 0.45, 0.22, 0, 0.42, -0.79, colour);
      box(g, 0.2, 0.25, 0.9, -w / 2 + 0.1, 0.42, -0.45, colour);
      box(g, 0.2, 0.25, 0.9, w / 2 - 0.1, 0.42, -0.45, colour);
      const seats = Math.max(2, Math.round(w / 0.8));
      const seat = (w - 0.4) / seats;
      for (let i = 0; i < seats; i++) {
        box(
          g,
          seat - 0.03,
          0.12,
          0.62,
          -w / 2 + 0.2 + seat * (i + 0.5),
          0.42,
          -0.36,
          tidy(colour, 0.08),
        );
      }
      return 0.9;
    },
    chair(g, it) {
      const colour = tidy(it.color, 0.1);
      for (const [x, z] of [
        [-0.2, -0.05],
        [0.2, -0.05],
        [-0.2, -0.43],
        [0.2, -0.43],
      ]) {
        box(g, 0.04, 0.44, 0.04, x, 0, z, DARK);
      }
      box(g, 0.46, 0.05, 0.46, 0, 0.44, -0.24, colour);
      box(g, 0.46, 0.45, 0.05, 0, 0.49, -0.45, colour);
      return 0.48;
    },
    table(g, it) {
      const w = clamp(it.width, 0.8, 2.2);
      const d = clamp(w * 0.55, 0.7, 1.0);
      box(g, w, 0.04, d, 0, 0.72, -d / 2, tidy(it.color, 0.1));
      for (const [sx, sz] of [
        [-1, 1],
        [1, 1],
        [-1, -1],
        [1, -1],
      ]) {
        box(g, 0.05, 0.72, 0.05, (sx * (w - 0.1)) / 2, 0, -d / 2 + (sz * (d - 0.1)) / 2, DARK);
      }
      return d;
    },
    tv(g, it) {
      const w = clamp(it.width, 0.6, 1.8);
      const y = Math.max(0.5, it.bottom);
      box(g, w, w * 0.58, 0.05, 0, y, -0.03, DARK, 0.3);
      if (y < 1.1) box(g, Math.max(1.2, w + 0.3), 0.45, 0.4, 0, 0, -0.2, WHITE);
      return 0.4;
    },
    fridge(g) {
      box(g, 0.7, 1.85, 0.66, 0, 0, -0.33, STEEL, 0.35);
      box(g, 0.66, 0.01, 0.01, 0, 1.2, 0.005, DARK);
      return 0.66;
    },
    oven(g) {
      box(g, 0.6, 0.88, 0.6, 0, 0, -0.3, STEEL, 0.4);
      box(g, 0.5, 0.35, 0.01, 0, 0.3, 0.005, DARK, 0.3);
      return 0.6;
    },
    microwave(g, it) {
      box(g, 0.5, 0.3, 0.38, 0, Math.max(0.9, it.bottom), -0.19, STEEL, 0.4);
      return 0.38;
    },
    sink(g) {
      box(g, 0.8, 0.86, 0.6, 0, 0, -0.3, WHITE);
      box(g, 0.5, 0.02, 0.35, 0, 0.86, -0.3, STEEL, 0.3);
      return 0.6;
    },
    toilet(g) {
      cylinder(g, 0.2, 0.4, 0, 0, -0.3, WHITE);
      box(g, 0.4, 0.4, 0.18, 0, 0.4, -0.6, WHITE);
      return 0.7;
    },
    plant(g) {
      cylinder(g, 0.16, 0.3, 0, 0, -0.18, [0.7, 0.5, 0.35]);
      const leaves = new THREE.Mesh(
        new THREE.IcosahedronGeometry(0.32, 1),
        material([0.3, 0.5, 0.28]),
      );
      leaves.position.set(0, 0.62, -0.18);
      g.add(leaves);
      return 0.36;
    },
  };
  const AGAINST_WALL = new Set(["bed", "sofa", "fridge", "oven", "sink", "tv", "toilet"]);

  for (const item of layout.items) {
    const build = builders[item.type];
    if (!build) continue;
    const group = new THREE.Group();
    group.name = item.type;
    const pieceDepth = build(group, item);
    let z = clamp(item.z, front + 0.1, room.back - pieceDepth);
    // Large pieces close to the back wall stand against it.
    if (AGAINST_WALL.has(item.type) && room.back - (z + pieceDepth) < 0.8)
      z = room.back - pieceDepth;
    group.position.set(clamp(item.x, room.left + 0.4, room.right - 0.4), 0, -z);
    scene.add(group);
  }
  return scene;
}

function exportGlb(scene) {
  return new Promise((resolve, reject) => {
    new GLTFExporter().parse(scene, (glb) => resolve(Buffer.from(glb)), reject, { binary: true });
  });
}

for (const path of process.argv.slice(2)) {
  const layout = JSON.parse(readFileSync(path, "utf8"));
  writeFileSync(path.replace(/\.json$/, ".glb"), await exportGlb(buildRoom(layout)));
}
