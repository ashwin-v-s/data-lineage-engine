# Observatory 3D assets

All assets here are **CC0 / public domain** and were downloaded at the sizes
noted below for the lineage observatory scene.

| File | Source | Licence |
| --- | --- | --- |
| `hdri/mpumalanga_veld_puresky_1k.hdr` | [mpumalanga_veld_puresky](https://polyhaven.com/a/mpumalanga_veld_puresky) | CC0 |
| `textures/grass/grass005_diff_2k.jpg` | [Grass005](https://ambientcg.com/view?id=Grass005) | CC0 |
| `textures/grass/grass005_nor_gl_1k.jpg` | [Grass005](https://ambientcg.com/view?id=Grass005) | CC0 |
| `textures/grass/grass005_rough_1k.jpg` | [Grass005](https://ambientcg.com/view?id=Grass005) | CC0 |
| `textures/bark/bark_brown_02_diff_2k.jpg` | [bark_brown_02](https://polyhaven.com/a/bark_brown_02) | CC0 |

The grass colour map was re-encoded from ambientCG's 2K JPG, the normal and
roughness maps from its 1K JPG; the bark diffuse map is Poly Haven's 2K JPG
re-encoded. Re-encoding only reduces file size — no content is changed. The
renderer repeats the lawn every 9 m so blades stay legible at eye height
without shimmering.

The HDRI is parsed in the browser by `frontend/observatory.js` (Radiance RGBE,
no extra loader) and prefiltered with three's `PMREMGenerator` for image-based
lighting. The grass diffuse/normal/roughness maps and the bark diffuse map are
applied to the terrain and trunks; every asset is optional and the scene falls
back to its procedural sky and painted lawn if a request fails.
