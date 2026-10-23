# Jupiter Atmosphere Simulation — Research Report

## A. Existing open-source code

| Repo / project | What it actually does | Stack, license, stars | Verdict |
|---|---|---|---|
| [Eluvade/cosmos](https://github.com/Eluvade/cosmos) | Procedural body generator; `GasGiant`/`GasGiantRinged` are FBM/domain-noise band shaders with seeded palettes and a `time` uniform. No velocity field, no advection, no vortices. | TypeScript, WebGL1, MIT, ~10★ | Usable as a base — for shader scaffolding and palette plumbing only, not dynamics |
| [THRASTRO/thrastro-shaders](https://github.com/THRASTRO/thrastro-shaders) | THREE.js planet/eclipse/atmosphere/ring shaders: per-fragment eclipse shadowing, night maps, Rayleigh/Mie atmosphere. Requires patched THREE.js versions. No flow. | JS/GLSL, license not stated in README | Reference only — for sphere shading, limb and eclipse, not atmosphere motion |
| [huazhige/Ge-et-al-water-Jupiter](https://github.com/huazhige/Ge-et-al-water-Jupiter) | Source for Ge et al. 2022, "Water controls heat transport in Jupiter's atmosphere" — a deep-atmosphere GCM configuration. | C++, BSD-3, 0★ | Reference only (scientific/offline) |
| [Adrien-Cb/JupiRSW](https://github.com/Adrien-Cb/JupiRSW) · [alihyder727/shallow-water-jupiter](https://github.com/alihyder727/shallow-water-jupiter) · [chengcli/2021.JupiterPolarVortex](https://github.com/chengcli/2021.JupiterPolarVortex) · [tanisha-gg/Simulating-Vortices-on-Jupiter](https://github.com/tanisha-gg/Simulating-Vortices-on-Jupiter) | Jupiter rotating-shallow-water models (polar vortices, GRS) in Python/Pencil; one is 1-D. CPU, batch, Matplotlib output. | Python, MIT/1★, none/1★, none/0★, none/0★ | Reference only (scientific/offline) |
| [awawa88/juno-layers](https://github.com/awawa88/juno-layers) | "Peelable" Three.js Jupiter: cloud deck shell, GRS, interior layers. Static/rotating textures. | TypeScript, no license, 0★ | Visual only, no dynamics |
| [SIGGRAPH 2015: Wrangling a Gas Giant for Jupiter Ascending](https://history.siggraph.org/wp-content/uploads/2022/10/2015-Talks-Keip_Wrangling-a-Gas-Giant-for-Jupiter-Ascending.pdf) | One-page talk abstract, Double Negative. No code. Describes *Timeless Advection* (non-divergent sculpted velocity field, density advected with strength-as-function-of-time, history-free so frames distribute), Volume UVs, diced clustered sims. | Film VFX, ACM DL | Reference only — the technique transfers, the asset does not |

**Leads that do not pan out.** *tosijs 3d gas-giant*: `3d.tosijs.net` and the `tosijs-3d` npm page were unreachable behind bot protection; I could not verify the demo exists as described. *emergentmind "Jovian bands"*: [that URL 404s](https://www.emergentmind.com/topics/jovian-bands); the site's Jupiter pages are AI-written literature summaries with no code. *Shadertoy*: search returned HTTP 403; I found no shader that simulates Jovian flow, only procedural band shaders.

**Nothing found combines real-time WebGL rendering with Jovian fluid dynamics.**

## B. Physical wind data

### Zonal wind u(latitude), cloud tops (~0.7–1.0 bar), System III

**Explicit caveat:** I could not obtain a machine-readable table — the closest ([UPC thesis appendix tables 11–25](https://upcommons.upc.edu/bitstream/handle/2117/360558/Shallow_Water_Report_fitxer%20de%20consulta.pdf?sequence=4), digitised from [Figure 6.2 of Ingersoll et al., *Dynamics of Jupiter's Atmosphere*](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)) sits past my accessible page range, and I cannot render figures. **The table below is an approximate reconstruction**, constrained to the quoted anchors, not a pixel digitisation. Treat it as ±15–20 m/s art-direction data.

| lat | u | lat | u |
|---|---|---|---|
| 90 | 0 | −5 | 140 |
| 85 | 3 | −10 | 100 |
| 80 | 8 | −15 | −25 |
| 75 | 12 | −20 | **−100** |
| 70 | 15 | −25 | −55 |
| 65 | 10 | −30 | 25 |
| 60 | 22 | −35 | 40 |
| 55 | 15 | −40 | 20 |
| 50 | 5 | −45 | −25 |
| 45 | −18 | −50 | 10 |
| 40 | 8 | −55 | 22 |
| 35 | 30 | −60 | 10 |
| 30 | **−30** | −65 | 5 |
| 25 | 140 | −70 | 12 |
| 20 | 45 | −75 | 8 |
| 15 | −12 | −80 | 5 |
| 10 | 105 | −85 | 2 |
| 5 | **140** | −90 | 0 |
| 0 | 55 | | |

Anchors: eastward jets bound the Equatorial Zone at **±7° PG** and the **equator is a local velocity *minimum*** ([Ingersoll et al., §6.2.1, 6.6.6](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)); the **23°N jet fell from 180 to 140 m/s between 1979 and 1995** ([ibid., §6.2.3](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)); the **24°N jet is the fastest prograde jet, >170 m/s** ([Sankar et al. 2021](https://arxiv.org/abs/2106.07809)); global scale "on the order of 100 m/s" ([Cao et al. 2023](https://arxiv.org/abs/2311.11494)). System III = 9 h 55 m 29.71 s ([Ingersoll et al.](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)). **Peak equatorial jet ≈140 m/s at ±7°**; main mid-latitude jets: +140–180 at 23–24°N, −100 at ~20°S, +40 at 33–35°S, −30 at 30°N.

### Great Red Spot
22.5°S PG, spanning 17°S–27.5°S ([Ingersoll et al. §6.3.1](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)). East–west length **17,000 km** (was 39,000 km in 1880; N–S 12,500 km) ([ibid.](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)); **16,350 km** as of 3 Apr 2017 ([NASA/Juno](https://en.wikipedia.org/wiki/Great_Red_Spot)). Peripheral wind **120 m/s** max in 1979 ([Ingersoll](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)) — consistent with 432 km/h ≈ 120 m/s, up to 496 km/h ≈ 138 m/s ([GRS](https://en.wikipedia.org/wiki/Great_Red_Spot)). Counterclockwise period **~4.5 Earth days** ([Rogers 2008, via GRS](https://en.wikipedia.org/wiki/Great_Red_Spot)). Longitude: **0.30°/day westward** — derivable from System II (9 h 55 m 42 s) vs System III (9 h 55 m 29.71 s), i.e. **≈4 m/s**, matching the observed **3.9 m/s** ([Abimbola 2025](https://arxiv.org/abs/2512.21928)); plus a 90-day, ~1° peak-to-peak longitude oscillation ([Ingersoll](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)).

### Other vortices for placement
White ovals at **33°S** (axes ~5,000 × 10,000 km), others at **41°S, 34°N, 40°N, 45°N**; major diameters 1,000 to >5,000 km ([Ingersoll §6.3.2](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)). Oval BA is the 33°S merged descendant. Brown **barges**: elongated cyclonic dark ovals, zonal extent **~5,000 km**, in the NEB ([Ingersoll §6.3.3](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)). 5-µm hot spots: cloud holes ~5,000 km wide near 6.5°N ([ibid.](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)).

### Vertical shear — justifies a 2-layer parallax
Cloud-tracked winds refer to **0.7–1.0 bar** ([Ingersoll §6.2.3](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)). Above 680 hPa the wind **decays to zero over ~2.4 scale heights**; at 180 hPa the 24°N jet is only **70–80 m/s** against >170 at the cloud deck ([Sankar et al. 2021](https://arxiv.org/abs/2106.07809)). Galileo probe: wind **increases with height to ~150 m/s** above the cloud deck ([Watkins & Cho 2013](https://arxiv.org/abs/1303.2022)); in the stratosphere there is a **200 m/s westward jet at 4 mbar** at the equator ([Benmahi et al. 2021](https://arxiv.org/abs/2107.06122)). **Yes — decks at different altitudes genuinely move at different speeds, by 50–100 m/s.**

## C. Technique references for real-time flow

1. **Domain warping / FBM in equirect UV** — cheap band turbulence; artifacts: pole pinching and the ±180° seam.
2. **Curl noise advection** — divergence-free 2D flow; scale longitude by `1/cos(lat)` or motion is wrong near poles.
3. **Flow maps (RG offsets + B time)** — classic band shear; needs an x-periodic texture and blending to avoid discontinuities.
4. **Semi-Lagrangian advection into a ping-pong float FBO** — real transport, no dissipation-free shortcut; artifacts: blurring, wraparound at the seam.
5. **Layered decks with distinct u(lat) profiles** — delivers the parallax; artifacts: double edges, opacity ordering.
6. **Timeless advection** ([SIGGRAPH 2015](https://history.siggraph.org/wp-content/uploads/2022/10/2015-Talks-Keip_Wrangling-a-Gas-Giant-for-Jupiter-Ascending.pdf)) — precompute a non-divergent field, advect with strength as a function of time, history-free; maps directly to an analytic divergence-free UV field; artifact: no vortex merging or filament shedding.

## Bottom line

**No drop-in real-time Jupiter atmosphere simulation exists** — the open-source landscape splits cleanly into offline scientific shallow-water/GCM code and purely visual gas-giant shaders, with no bridge between them. What you should build from scratch is a two-layer GPU advection system on your existing sphere: a divergence-free velocity field assembled from the digitised u(lat) profile plus curl-noise eddies and explicit vortex discs at 22.5°S, 33°S and the NEB barge latitudes, advecting one albedo texture per deck semi-Lagrangian in a ping-pong FBO. Keep the existing geometry, camera and NASA map sampling; replace only the texture-coordinate rotation with `uv.x -= u(lat)·dt / (2πR cos lat)` per layer, then let the curl-noise term supply the vortices you cannot fit analytically.
