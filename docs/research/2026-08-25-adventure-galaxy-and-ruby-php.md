# Adventure galaxy and Ruby/PHP evidence — pinned inspiration

Date: 2026-08-25

This record separates ideas studied from code shipped. Codemble's implementation
was written independently. No source code, shader, texture, model, screenshot,
or other asset was copied into the repository.

## Sources inspected

| Source | Pinned revision | License | What informed the work |
| --- | --- | --- | --- |
| [tree-sitter-ruby](https://github.com/tree-sitter/tree-sitter-ruby/tree/ad907a69da0c8a4f7a943a7fe012712208da6dee) | `ad907a69da0c8a4f7a943a7fe012712208da6dee` | [MIT](https://github.com/tree-sitter/tree-sitter-ruby/blob/ad907a69da0c8a4f7a943a7fe012712208da6dee/LICENSE) | Official Ruby grammar shapes and package boundary |
| [tree-sitter-php](https://github.com/tree-sitter/tree-sitter-php/tree/3fda2fb9577166c6399834917f9844f30370beea) | `3fda2fb9577166c6399834917f9844f30370beea` | [MIT](https://github.com/tree-sitter/tree-sitter-php/blob/3fda2fb9577166c6399834917f9844f30370beea/LICENSE) | Official PHP grammar shapes and package boundary |
| [three.js sky example](https://github.com/mrdoob/three.js/blob/21585c3021567e7284f1c881b392208a11264a63/examples/webgl_shaders_sky.html) | `21585c3021567e7284f1c881b392208a11264a63` | [MIT](https://github.com/mrdoob/three.js/blob/21585c3021567e7284f1c881b392208a11264a63/LICENSE) | Layered atmospheric depth and explicitly decorative shader separation |

## Adopted principles

- Use official grammar wheels behind Codemble's existing adapter seam.
- Keep extraction passes deterministic and make unresolved dynamic dispatch
  possible rather than certain.
- Treat syntax errors as a fail-closed evidence boundary.
- Build atmosphere from multiple depth layers while keeping every gameplay and
  correctness channel outside the decorative shader.
- Seed all scenery from stable graph identity and dispose every created GPU
  resource with the scene it belongs to.

## Deliberately rejected

- Copying grammar-query code, shaders, textures, models, or assets.
- Pulling a game engine or another graph renderer into the runtime.
- Free-flight controls, procedural per-system surfaces at Galaxy scale, random
  layouts, scores, XP, streaks, or visuals that imply certainty.
- Treating Rails or Laravel behavior as a parser rule merely because a familiar
  name appears; framework roles still require explicit evidence.

## Corpus receipts

- Rails `1f0c247be3da6c40332df94a4d1d2efdaaf7260c`: 3,452 Ruby files,
  53,478 nodes, 298,355 edges, 95,496 concepts, zero partial files, 21.760 s.
- Laravel Framework `9b21ce0a9bb2b2599978bc0b0df4abea952ad31c`:
  3,034 PHP files, 38,540 nodes, 207,232 edges, 5,716 concepts, one partial
  file, 43.573 s.

Both immediate repeats produced deterministic output. These are pinned
engineering receipts, not claims of exhaustive Ruby or PHP semantics.
