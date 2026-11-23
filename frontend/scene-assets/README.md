# Observatory 3D assets

All assets here are **CC0 / public domain** from [Poly Haven](https://polyhaven.com) and
were downloaded at 1K resolution for the lineage observatory scene.

| File | Source | Licence |
| --- | --- | --- |
| `hdri/mpumalanga_veld_puresky_1k.hdr` | [mpumalanga_veld_puresky](https://polyhaven.com/a/mpumalanga_veld_puresky) | CC0 |
| `textures/grass/leafy_grass_*.jpg` | [leafy_grass](https://polyhaven.com/a/leafy_grass) | CC0 |
| `textures/bark/bark_brown_02_diff_1k.jpg` | [bark_brown_02](https://polyhaven.com/a/bark_brown_02) | CC0 |

The HDRI is parsed in the browser by `frontend/observatory.js` (Radiance RGBE,
no extra loader) and prefiltered with three's `PMREMGenerator` for image-based
lighting. The grass diffuse/normal/roughness maps and the bark diffuse map are
applied to the terrain and trunks; every asset is optional and the scene falls
back to its procedural sky and painted lawn if a request fails.
