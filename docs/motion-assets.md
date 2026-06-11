# Motion Asset Intake

Repo to Shorts keeps small SVG motion accents in `renderer/public/motion/` and treats complex Lottie files as local user assets.

## License Boundary

- LottieFiles: prefer assets that can be downloaded under the [LottieFiles Simple License](https://lottiefiles.com/page/license). Record the source URL when importing.
- IconScout, Envato Elements, and Lordicon: use local import only. Do not commit downloaded JSON source files into this repository unless the license explicitly allows redistribution as project assets. See [IconScout licenses](https://iconscout.com/licenses), [Envato Elements license terms](https://elements.envato.com/license-terms), and [Lordicon licenses](https://lordicon.com/licenses).
- Current default catalog intentionally contains no bundled complex Lottie files. This avoids shipping visually mismatched sample animations as product defaults.

## Visual Screen

Accept:

- Computer, code, terminal, repository, dashboard, data-flow, document search, file scan, or online learning topics.
- Transparent background or sparse particles/lines.
- Dark or muted palette, or assets that still look good after renderer-side dimming.
- JSON smaller than about 800KB.

Reject:

- Big colored rectangles, full-canvas solid layers, framed mockups, bright cartoon palettes, large logo marks, and marketplace watermarks.
- Assets whose visible text would conflict with generated Chinese storyboard text.
- CTA assets that compete with the repository name or final call to action.

## Candidate Directions

| Direction | Source | Search phrase | Preferred layouts |
| --- | --- | --- | --- |
| Dark laptop coding | LottieFiles | `dark laptop coding lottie` | `code`, `steps`, `stack` |
| Developer at laptop | LottieFiles | `developer laptop code lottie` | `github_hero`, `feature_spotlight` |
| Data dashboard | LottieFiles | `dark dashboard analytics lottie` | `github_hero`, `feature_spotlight` |
| Network data flow | LottieFiles | `network data flow lottie` | `architecture_map`, `flow` |
| Pipeline / automation | LottieFiles | `pipeline automation lottie` | `architecture_map`, `flow`, `steps` |
| Document search | LottieFiles | `document search scan lottie` | `readme_focus`, `evidence_grid` |
| File indexing | LottieFiles | `file scan indexing lottie` | `readme_focus`, `evidence_grid` |
| Online learning laptop | IconScout | `online learning laptop lottie` | `title`, `feature_spotlight` |
| Programming laptop | IconScout | `programming laptop lottie` | `code`, `stack` |
| Outline laptop/code accent | Lordicon | `wired outline laptop code` | `code`, `cta` as small accent only |
| Dark data dashboard JSON | Envato Elements | `dark data dashboard lottie animation json` | `github_hero`, `architecture_map` |
| Computer learning JSON | Envato Elements | `computer learning lottie animation json` | `title`, `feature_spotlight` |

## Import Examples

```powershell
gva motion import .\downloads\developer-laptop.json --name developer-laptop.json --role side_illustration --tags code,developer --layouts code,steps,stack --source-url https://example.com/source --license "user-provided"
```

```powershell
gva motion import .\downloads\document-search.zip --role hero_background --tags readme,search,evidence --layouts readme_focus,evidence_grid --source-url https://example.com/source --license "user-provided"
```

The importer skips same-name files, validates required Lottie keys, rejects large files, and rejects obvious full-canvas backgrounds.
