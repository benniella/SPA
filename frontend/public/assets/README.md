# Static assets

Served from the site root. '/assets/logos/spa-mark.svg' is the URL for the file
below.

'''
public/
└── assets/
├── images/ marketing imagery, screenshots, illustrations
├── videos/ hero video, analysis demonstrations, marketing clips
├── logos/ brand marks and favicons
└── icons/ local static icon files
'''

## Rules

1. **Nothing lives outside 'assets/'.** A file at 'public/logo.png' has no stated
   purpose; 'public/assets/logos/spa-mark.svg' does.
2. **Meaningful filenames.** 'spa-mark.svg', 'spa-mark-light.svg' — not
   'logo-final-2.svg'.
3. **No duplicates.** If two places need the same file, one of them imports the
   other's path via the brand module rather than a second copy being added.
4. **Optimise before committing.** 'images/' is for raster art that has already
   been compressed; 'logos/' is for vector marks, which should stay vector.

## What is here

| File                       | Purpose                               |
| -------------------------- | ------------------------------------- |
| 'logos/spa-mark.svg'       | The brand mark, dark-surface variant  |
| 'logos/spa-mark-light.svg' | The brand mark, light-surface variant |
| 'logos/spa-mark-192.png'   | PWA icon                              |
| 'logos/spa-mark-512.png'   | PWA icon                              |
| 'logos/favicon.svg'        | Favicon source                        |
| 'videos/video.mp4'         | Landing page hero recording           |
| 'videos/video-poster.jpg'  | First frame of the above, as poster   |

'images/' and 'icons/' are empty. Nothing has been added to fill them: SPA's
visualizations are drawn as SVG in the components, which is cheaper than a
screenshot and stays sharp at any size. They exist so that the first real asset
has an obvious home rather than being dropped in a component folder.

The hero video is 864x496 H.264 at ~1.7 Mbps. Its intrinsic size is declared in
'data/marketing.ts' as 'HERO_VIDEO' so the browser reserves the box before the
first frame arrives, and the poster is regenerated with:

'''
ffmpeg -i video.mp4 -frames:v 1 -q:v 3 video-poster.jpg
'''
