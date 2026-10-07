# Music atlas — multi-label style navigation

Music page source and generated static assets for GitHub Pages.

## Completion boundary

All 878 playlist IDs are in the catalog and graph. Public playlist IDs were
reconciled against the local snapshot without missing or extra IDs. Advertised
platform counts may fluctuate and are not used to invent extra songs.

**This is not the completed 878-track musical interpretation requested by the
owner.** The prior 69-track sample also contains listening questions, rather than
completed track-by-track listening. Its 112 candidate links retain that status.
789 tracks remain explicitly pending editorial interpretation.

The initial full-catalog experiment incorrectly let numerical feature clusters
lead the musical composition. That was rejected by the owner. The non-style views keep
the original six editorial exploration regions and original notes. The default
style view arranges songs by sourced multi-label genre context. Unreviewed
tracks are distributed by catalog relationships without assigning invented genres.
Acoustic measurements and keyword statistics are secondary expandable information,
with separate optional graph layers. No automatic measurement is called a finished
listening interpretation.

## Sources and evidence

- `_data/music.json`: original playlist metadata; never overwritten by collection.
- `_data/music_atlas.json`: stable-ID editorial notes, sources and candidate links.
- `_data/music_evidence.json`: derived per-track measurements and provenance;
  no full lyrics, audio files, signed playback URLs or account credentials.
- `catalog.json`: 878 tracks in original playlist order.
- `network.json`: 878 nodes and 3009 typed edges at this snapshot. 289 same-album
  and 829 same-artist relations are identity facts. 720 excerpt acoustic links are
  measurements, 48 keyword links and 112 editorial links remain candidates.
- Audio excerpts were measured for 594 tracks. The public API did not provide
  suitable audio for 284 tracks; no acoustic links are inferred for them.
- Lyrics were available for 736 tracks. 114 other tracks were labelled instrumental
  by the platform, which is not independent proof that vocals are absent.
- Sampling measures two approximately 20-second MP3 byte ranges at 25% and 65%.
  Byte positions only approximate chronological position for variable bitrate MP3s.
  Mono 16 kHz STFT descriptors cover centroid, bandwidth, flatness, low/high energy,
  frame-energy spread and spectral flux. These are not instruments, emotion,
  musical section labels, exact tempo, melody, harmony or full-track listening.
- Acoustic edges require mutual four-nearest-neighbor membership and RMS distance
  at most .9 in seven transformed dimensions. Log transforms, 1/99-percentile
  winsorization, population z-scores and +/-3 clipping are recorded in the output.
- Text links need at least two shared keyword themes, each with two distinct terms,
  and are capped at two links per track. They do not resolve negation or metaphor.
- The default style view uses artist/release/track sources as explicitly scoped
  navigation context. Artist-level labels remain inferred for each track, not
  listening-confirmed classifications.
- Raw API caches are ignored under `local/music-atlas/evidence`. Audio excerpts
  exist only in memory while measuring and are not saved or redistributed.

## Rendering and design

Coordinates are precomputed during the Python build with deterministic spatial
packing, identity springs and collision relaxation. No force iterations run on
the browser's main thread. ID sorting preserves layout after playlist reordering.
PageRank is equal-weight and undirected over all typed relations, including
candidates (damping .85); logarithmic radius 20–28 world units. It is not popularity
or preference. Parallel relation types count as distinct edge records; PageRank
adjacency treats an endpoint pair as one neighbor.

The graph draws at most 220 edges at a time and labels at most 28 desktop / 10
mobile songs. Labels are created on demand and avoid covers and region titles.
Offscreen nodes are hidden. Overview artwork uses Hugging Face 64px previews, switching
to 512px on zoom. The dataset stores 718 untouched original files plus both
preview sizes. Clicking the detail cover opens the original. GitHub stores only
URLs and a checked-in `_data/music_artwork.json` manifest; builds never write
raster artwork into tracked folders. URLs are pinned to a verified HF revision.
Thin perimeter colors are sampled from the outer 8% of artwork.

Every load defaults to static. Explicit optional motion moves region layers,
rather than editing 878 node transforms every frame, and updates only drawn edges.
Highlight freezes all layers; a second click on the same node clears it and resumes
the previous motion setting. Escape and close clear selection. Background tabs,
offscreen maps, list view and dragging pause motion. Reduced-motion defaults static
and allows explicit opt-in. SVG geometry stays consistent with hit targets.

The intro preserves the title / Last Tide collage / right statement composition.
The supplied Hugging Face collage is referenced directly without crop/color filters;
clicking opens its 4096×2731 asset. Mobile places it below the title. Fonts are local
with their SIL notices. The graph needs no third-party JavaScript runtime.


## Multi-label style view

Default connection mode is 风格; default motion remains static. Every playlist ID
has a style state. At this snapshot, 713 / 878 tracks have source-backed
style labels; 165 remain 风格待确认. There are 156 observed genre labels.
Unknown is a status, never a similarity label. No claim of full per-track listening.

Sources are stored in `_data/music_style_sources.json` (MusicBrainz),
`music_wiki_style_sources.json` (artist infobox fields),
`music_yaogun_style_sources.json` (Chinese Rock Database genre fields), and
`music_style_overrides.json` (curated URLs and stable-ID song corrections).
Country/language/year tags are rejected. Low-vote MusicBrainz outliers are excluded
relative to the artist's dominant genre votes. Known same-name mismatches, including
Swiss Sadness versus the US project, are rejected. These remain navigation hints.

Genres retain parent labels, e.g. Midwest Emo → Emo → Rock, without inventing
sibling tags such as Math Rock. The UI supports searchable AND multi-selection.
One song has one node; its primary style sets its region, other direct genre labels
create candidate bridges. Edges require a shared specific direct genre, exclude
broad roots and pending status, and are capped at three per node. Scores combine
inverse label frequency and label-set overlap, with a same-artist discount.
Elliptical star groups and cover collision relaxation run only during the build.

To refresh artist sources before rebuilding:

```sh
python scripts/collect_music_styles.py
python scripts/collect_music_wiki_styles.py
python scripts/collect_music_yaogun_styles.py
python scripts/build_music_atlas.py
```

A track override can contain `exclude`, `primary`, and `labels` entries with
`id`, `url`, `title`, and `basis`; these receive track-level provenance. Artist
entries only receive release scope for exact `albums` name matches. Source caches
remain ignored under `local/music-atlas/`.


## External media storage

Music raster files belong in `edzee3000/GithubData` under
`homepage-assets/music/atlas`, rather than in GitHub. Upload preserves each
original's bytes and SHA256, creates 512px/64px browser previews under ignored
`local/`, checks all remote file sizes and original LFS/Git blob hashes, and writes the
small URL manifest only after verification. Existing Last Tide mosaic already
uses the same dataset. Tiny code-authored SVG fallback remains in GitHub.

```sh
# Requires an authenticated HF account with write access to the owner's dataset.
python scripts/upload_music_artwork.py --archive ../music-artwork
python scripts/build_music_atlas.py
```

Do not commit original images, videos, or generated raster previews. Original
source cover dimensions vary; originals are never upscaled or recompressed.
The build/import has no HF authentication or upload dependency. The upload tool
requires huggingface_hub and uses the local authenticated session; credentials
are never written into website assets.

## Rebuild and collect

```sh
python -m pip install -r scripts/requirements-music-atlas.txt
python scripts/collect_music_evidence.py
python scripts/build_music_atlas.py
python scripts/build_music_atlas.py --check
python -m unittest discover -s scripts/tests
```

Collection uses public unauthenticated NetEase endpoints, bounded range requests
and ffmpeg. It does not bypass unavailable audio or paid access. Cached unavailable
results are explicit. ffmpeg is needed only for fresh audio measurement; checked-in
website output has no Python runtime dependency. The external artwork archive is
only needed for uploading new covers. Normal builds use the checked-in URL manifest.

```sh
python scripts/import_music_tracks.py exported-playlist.json
python scripts/import_music_tracks.py --playlist-id 8114560070
```

Imports preview by default; `--apply` writes and rebuilds. Stable IDs preserve
editorial annotations. Duplicate or incomplete metadata aborts. New songs remain
pending; they do not acquire guessed sound/genre/emotion interpretations. Backups
live under ignored `local/`. New covers use their external source URL until an original has been archived
and uploaded; no build/import writes image binaries into GitHub.

```sh
python scripts/preview_music_atlas.py --port 4173
```

Local preview renders the actual include with relative-URL substitution. It is not
a full Jekyll build; Ruby is unavailable and the full site build remains unverified.

Thirteen data tests pass, including stable imports, PageRank mass, evidence boundaries,
missing-lyrics handling, known-frequency signal measurement and full graph IDs.
Actual browser checks cover 878 nodes, edge budget, search, mobile overflow,
static default, highlight hold and repeated-click resume, with no page errors.
Local reports: `local/music-atlas/full-verification.json`. Historical v5 timings
measure the old browser layout and must not be presented as current timings.

Remaining: genuine track-by-track interpretation, stronger primary release/track
sources, complete audio where legitimately available, listening-reviewed similarity
links, full Jekyll verification and publication.
