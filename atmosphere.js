/* Real-time Jovian atmospheric flow for the Jupiter wallpaper.
 *
 * The planet geometry, lighting and rotation counter stay in wallpaper.js.
 * This file only changes how the global map is sampled: the lookup point is
 * displaced by a wind field instead of moving as one rigid texture.
 *
 * Three effects, cheapest first:
 *   1. Zonal jets  - u(latitude) from Jupiter's measured jet structure shears
 *                    the photographed cloud deck.  The displacement is bounded
 *                    so a still photograph never winds itself into oblivion.
 *   2. Vortices    - analytic elliptical swirls centred on the Great Red Spot
 *                    and the white ovals.  Rotation is periodic, so it can run
 *                    for weeks without accumulating error.
 *   3. Tracers     - a precomputed curl-noise field streaming with the local
 *                    jet, giving filaments and eddies inside the bands.
 *
 * Everything is a pure function of the simulated time: no feedback buffers, so
 * the wallpaper is deterministic, never blurs, and costs two extra texture
 * fetches per pixel.
 */
window.JupiterAtmosphere = (function () {
  'use strict';

  /* ------------------------------------------------------------------ *
   * 用户可直接修改的设置（改完关闭壁纸再启动即可生效）
   * ------------------------------------------------------------------ */
  const CONFIG = {
    // true = 开启实时气流与涡旋；false = 退回原来「整张图刚性自转」的效果。
    // 运行中也可以随时切换：双击 toggle_weather.cmd，或按 Ctrl+Alt+J。
    LIVE_WEATHER: true,

    // 示踪流的相对速度。默认 2.5 与当前「约 36 秒自转一周」的桌面速度相称；
    // 若把自转调慢 10 倍（`periodMs` 乘 10），把它也调小 10 倍即可保持同样的观感。
    TRACER_SPEED: 2.5,

    // 云顶明暗对比。实时模式下由示踪场产生的亮度起伏强度，0 = 完全不用，
    // 0.5 左右比较自然，超过 1.0 会像电视雪花。
    CONTRAST: 0.5,

    // 涡旋扭转幅度倍率。1.0 = 大红斑内部与周围云带来回扭转约 ±31°（约 170 秒
    // 一个来回）；这是可回退的摆动，不会把贴图越卷越紧。
    VORTEX_SPIN: 1.0,

    // 湍流形变强度。「云带边缘被拉扯得多厉害」，0.6 温和，1.5 剧烈。
    TURBULENCE: 1.0,
  };

  /* ------------------------------------------------------------------ *
   * Jupiter zonal wind profile, u(latitude) in m/s (System III, +eastward).
   *
   * This is a smooth fit to the published jet structure, not a digitised
   * dataset: prograde/retrograde alternation, the ~100 m/s equatorial jet with
   * its local minimum at the equator, the strong prograde jet near 24 N, the
   * strong retrograde flow of the South Tropical region, and weak polar winds.
   * It is used for visual dynamics only.  Anchors: the equatorial zone is
   * bounded by the +-7 deg prograde jets with a local minimum at the equator;
   * the 24 N jet is the fastest prograde jet (>170 m/s, 140 m/s in the 1995
   * state); overall scale ~100 m/s.  Sources: Ingersoll et al., "Dynamics of
   * Jupiter's Atmosphere" (2004) ch. 6; Porco et al. 2003 (Science 299, 1541);
   * Sankar et al. 2021 (arXiv:2106.07809); BAA Jupiter Section jet list.
   * ------------------------------------------------------------------ */
  const PROFILE = [
    [90, 0], [85, 0], [80, -2], [75, 3], [70, -4], [65, 5], [60, -6],
    [55, 8], [50, -12], [47, 6], [45, 14], [43, 10], [40, -14], [38, 16],
    [36, 24], [34, 12], [32, -18], [30, -30], [28, -21], [26, 60],
    [25, 120], [24, 168], [23, 140], [22, 55], [20, -25], [18, -48],
    [16, -38], [14, -15], [12, 30], [10, 75], [8, 105], [6, 118], [4, 108],
    [2, 98], [0, 90], [-2, 96], [-4, 106], [-6, 112], [-8, 95], [-10, 40],
    [-12, -20], [-14, -45], [-16, -52], [-18, -45], [-20, -20], [-22, 8],
    [-24, 22], [-26, 32], [-28, 25], [-30, 6], [-32, -22], [-34, -32],
    [-36, -12], [-38, 8], [-40, -18], [-42, -8], [-44, 14], [-46, 18],
    [-48, 2], [-50, -10], [-52, 8], [-54, 4], [-56, -6], [-58, 6], [-60, 10],
    [-62, 4], [-64, -4], [-66, 5], [-68, 0], [-70, -3], [-72, 0], [-74, 4],
    [-76, 0], [-78, -3], [-80, 0], [-82, 2], [-84, 0], [-86, 0], [-88, 0],
    [-90, 0],
  ];

  /* ------------------------------------------------------------------ *
   * Vortex positions are measured from the playback maps by
   * analyze_vortices.py, in texture coordinates: u = x / width, v measured
   * from the south pole (0) to the north pole (1).  rx / ry are the ellipse
   * radii in uv units, twist is the peak twist in radians and period the
   * seconds of one full churn cycle at VORTEX_SPIN = 1.  Anticyclones in the
   * southern hemisphere turn clockwise with north up, hence spin = +1.
   * ------------------------------------------------------------------ */
  const VORTICES = {
    cassini: [
      // Great Red Spot, 22 S.  The 2000 Cassini mosaic shows its full hollow.
      { u: 0.3688, v: 0.3792, rx: 0.030, ry: 0.035, twist: 0.55, period: 170, spin: 1 },
      // White ovals in the South Temperate Zone.
      { u: 0.5208, v: 0.2944, rx: 0.012, ry: 0.014, twist: 0.8, period: 120, spin: 1 },
      { u: 0.2396, v: 0.2931, rx: 0.012, ry: 0.014, twist: 0.8, period: 135, spin: 1 },
      { u: 0.5625, v: 0.2958, rx: 0.011, ry: 0.013, twist: 0.8, period: 110, spin: 1 },
    ],
    hubble: [
      // Great Red Spot, 22 S in the 2015 Hubble map.
      { u: 0.6493, v: 0.3681, rx: 0.029, ry: 0.034, twist: 0.55, period: 170, spin: 1 },
      { u: 0.4299, v: 0.2736, rx: 0.012, ry: 0.014, twist: 0.8, period: 125, spin: 1 },
      { u: 0.7444, v: 0.2708, rx: 0.012, ry: 0.014, twist: 0.8, period: 140, spin: 1 },
      // Oval BA ("Red Jr."), 34 S, still small and pale in 2015.
      { u: 0.3292, v: 0.3111, rx: 0.013, ry: 0.015, twist: 0.7, period: 145, spin: 1 },
    ],
    merged: [
      { u: 0.8535, v: 0.3653, rx: 0.029, ry: 0.034, twist: 0.55, period: 170, spin: 1 },
      { u: 0.1210, v: 0.3190, rx: 0.013, ry: 0.015, twist: 0.7, period: 130, spin: 1 },
      { u: 0.0542, v: 0.2722, rx: 0.012, ry: 0.014, twist: 0.8, period: 125, spin: 1 },
      { u: 0.7736, v: 0.2750, rx: 0.012, ry: 0.014, twist: 0.8, period: 135, spin: 1 },
    ],
  };

  const MAX_VORTICES = 6;

  /* ------------------------------------------------------------------ *
   * Shaders
   * ------------------------------------------------------------------ */
  const GLSL = `
    uniform sampler2D u_wind;
    uniform sampler2D u_tracer;
    uniform float u_flowTime;
    uniform float u_live;
    uniform float u_turbulence;
    uniform float u_contrast;
    uniform float u_tracerSpeed;
    // xy = centre in texture uv, z = longitude radius, w = peak twist (rad)
    uniform vec4 u_vortexA[${MAX_VORTICES}];
    // x = latitude radius, y = twist period (s)
    uniform vec4 u_vortexB[${MAX_VORTICES}];

    // Returns the displaced map lookup in .xy and a cloud density in .z.
    vec3 jupiterAtmosphere(vec2 uv, float t) {
      vec4 wind = texture(u_wind, vec2(uv.y, 0.5));
      float speed = wind.r * 2.0 - 1.0;              // u / 200 m/s
      float edge = wind.g;                            // activity at jet edges
      float phase = wind.b * 6.2831853;

      // 1. The photographed deck churns back and forth inside each band.
      //    A bounded displacement cannot accumulate, so the mosaic stays
      //    recognisable for as long as the wallpaper runs.
      float amp = 0.0042 * (0.35 + 0.65 * min(abs(speed) * 1.5, 1.0));
      float omega = (0.05 + 0.06 * min(abs(speed), 1.0)) * sign(speed);
      float shear = -amp * sin(omega * t + phase);

      // 2. Vortices twist their own clouds and drag the collar.  The twist is
      //    a bounded oscillation, so a still mosaic never winds itself into a
      //    spiral no matter how long the wallpaper runs.
      vec2 vortex = vec2(0.0);
      for (int i = 0; i < ${MAX_VORTICES}; ++i) {
        vec4 a = u_vortexA[i];
        if (a.w == 0.0) continue;
        vec2 d = uv - a.xy;
        d.x -= floor(d.x + 0.5);                      // shortest way round
        vec2 e = d / vec2(a.z, u_vortexB[i].x);
        // Flat core, soft rim: the oval keeps its shape while the collar is
        // dragged around it, which reads like a real long-lived anticyclone.
        float w = 1.0 - smoothstep(0.45, 1.45, length(e));
        float period = max(u_vortexB[i].y, 1.0);
        float ang = a.w * sin(6.2831853 * t / period) * w;
        float c = cos(ang), s = sin(ang);
        vec2 r = vec2(c * e.x - s * e.y, s * e.x + c * e.y);
        vortex += (r - e) * vec2(a.z, u_vortexB[i].x);
      }

      // 3. Passive tracers stream with the local zonal jet.  The field is
      //    statistically homogeneous, so unbounded advection is safe here.
      float adv = -0.00035 * speed * u_tracerSpeed * t;
      vec2 p = vec2((uv.x + adv) * 2.0, uv.y * 7.0);
      vec4 n1 = texture(u_tracer, p * 0.61);
      vec4 n2 = texture(u_tracer, p * 0.37 + vec2(0.31, 0.67));
      vec2 curl = n1.rg + n2.rg - 1.0;
      float density = 0.62 * n1.b + 0.38 * n2.b;

      float warp = 0.0016 * u_turbulence * (0.35 + edge);
      vec2 offset = vec2(shear, 0.0) + vortex + curl * warp;
      return vec3(uv + offset, density);
    }
  `;

  /* ------------------------------------------------------------------ *
   * CPU side: wind lookup table and tracer field
   * ------------------------------------------------------------------ */
  const WIND_SAMPLES = 256;

  function windSpeedAt(latitude) {
    // Linear interpolation on the 5-degree table, then smoothed below.
    if (latitude >= PROFILE[0][0]) return PROFILE[0][1];
    for (let i = 1; i < PROFILE.length; i++) {
      const lat = PROFILE[i][0];
      if (latitude >= lat) {
        const lat0 = PROFILE[i - 1][0];
        const speed0 = PROFILE[i - 1][1];
        const speed = PROFILE[i][1];
        const f = (latitude - lat) / (lat0 - lat);
        return speed + (speed0 - speed) * f;
      }
    }
    return PROFILE[PROFILE.length - 1][1];
  }

  function buildWindPixels() {
    const speed = new Float32Array(WIND_SAMPLES);
    const activity = new Float32Array(WIND_SAMPLES);
    for (let i = 0; i < WIND_SAMPLES; i++) {
      const v = (i + 0.5) / WIND_SAMPLES;
      speed[i] = windSpeedAt((v - 0.5) * 180);
    }
    // A three-tap smooth keeps the shader's lookup table reads gentle.
    const smoothed = new Float32Array(WIND_SAMPLES);
    for (let i = 0; i < WIND_SAMPLES; i++) {
      const lo = speed[Math.max(0, i - 1)];
      const hi = speed[Math.min(WIND_SAMPLES - 1, i + 1)];
      smoothed[i] = (lo + 2 * speed[i] + hi) / 4;
    }
    speed.set(smoothed);
    // Turbulence follows the shear: band edges are where eddies live.
    let peak = 1e-6;
    for (let i = 0; i < WIND_SAMPLES; i++) {
      const lo = speed[Math.max(0, i - 2)];
      const hi = speed[Math.min(WIND_SAMPLES - 1, i + 2)];
      activity[i] = Math.abs(hi - lo);
      peak = Math.max(peak, activity[i]);
    }
    const pixels = new Uint8Array(WIND_SAMPLES * 4);
    for (let i = 0; i < WIND_SAMPLES; i++) {
      const v = (i + 0.5) / WIND_SAMPLES;
      const phase = 0.5 + 0.5 * Math.sin(v * 37.1) * Math.sin(v * 61.7 + 1.7);
      const normalized = Math.min(1, Math.max(0, speed[i] / 200 * 0.5 + 0.5));
      pixels[i * 4 + 0] = Math.round(normalized * 255);
      pixels[i * 4 + 1] = Math.round(Math.sqrt(Math.min(1, activity[i] / peak)) * 255);
      pixels[i * 4 + 2] = Math.round(phase * 255);
      pixels[i * 4 + 3] = 255;
    }
    return pixels;
  }

  function smoothstep01(t) {
    return t * t * (3 - 2 * t);
  }

  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function fillLattice(size, seed) {
    const random = mulberry32(seed);
    const lattice = new Float32Array(size * size);
    for (let i = 0; i < lattice.length; i++) lattice[i] = random();
    return lattice;
  }

  function buildTracerPixels(width, height) {
    const octaves = [
      { size: 8, amp: 1.0, seed: 0x9E3779B9 },
      { size: 16, amp: 0.62, seed: 0x85EBCA6B },
      { size: 32, amp: 0.4, seed: 0xC2B2AE35 },
      { size: 64, amp: 0.26, seed: 0x27D4EB2F },
      { size: 128, amp: 0.17, seed: 0x165667B1 },
    ].map(function (octave) {
      octave.lattice = fillLattice(octave.size, octave.seed);
      return octave;
    });

    const psi = new Float32Array(width * height);
    const xStep = 1 / width;
    const yStep = 1 / height;
    for (let y = 0; y < height; y++) {
      const fy = y * yStep;
      for (let x = 0; x < width; x++) {
        const fx = x * xStep;
        let value = 0;
        let norm = 0;
        for (let o = 0; o < octaves.length; o++) {
          const octave = octaves[o];
          const size = octave.size;
          const gx = fx * size;
          const gy = fy * size;
          const x0 = Math.floor(gx);
          const y0 = Math.floor(gy);
          const tx = smoothstep01(gx - x0);
          const ty = smoothstep01(gy - y0);
          const xa = x0 % size;
          const xb = (x0 + 1) % size;
          const i0 = (y0 % size) * size;
          const i1 = ((y0 + 1) % size) * size;
          const lattice = octave.lattice;
          const top = lattice[i0 + xa] * (1 - tx) + lattice[i0 + xb] * tx;
          const bottom = lattice[i1 + xa] * (1 - tx) + lattice[i1 + xb] * tx;
          value += (top * (1 - ty) + bottom * ty) * octave.amp;
          norm += octave.amp;
        }
        psi[y * width + x] = value / norm;
      }
    }

    // Curl of the stream function gives a divergence-free swirl field.
    const curlX = new Float32Array(width * height);
    const curlY = new Float32Array(width * height);
    let sum = 0;
    for (let y = 0; y < height; y++) {
      const up = ((y + 1) % height) * width;
      const down = ((y - 1 + height) % height) * width;
      for (let x = 0; x < width; x++) {
        const left = (x - 1 + width) % width;
        const right = (x + 1) % width;
        const dx = (psi[y * width + right] - psi[y * width + left]) * 0.5;
        const dy = (psi[up + x] - psi[down + x]) * 0.5;
        curlX[y * width + x] = dy;
        curlY[y * width + x] = -dx;
        sum += dx * dx + dy * dy;
      }
    }
    const rms = Math.sqrt(sum / (width * height)) * 2 + 1e-6;

    const pixels = new Uint8Array(width * height * 4);
    for (let i = 0; i < width * height; i++) {
      const cx = Math.max(-1, Math.min(1, curlX[i] / rms));
      const cy = Math.max(-1, Math.min(1, curlY[i] / rms));
      pixels[i * 4 + 0] = Math.round((cx * 0.5 + 0.5) * 255);
      pixels[i * 4 + 1] = Math.round((cy * 0.5 + 0.5) * 255);
      pixels[i * 4 + 2] = Math.round(Math.max(0, Math.min(1, psi[i])) * 255);
      pixels[i * 4 + 3] = 255;
    }
    return pixels;
  }

  function uploadTexture(gl, width, height, pixels, mipmap) {
    const texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, width, height, 0,
                  gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER,
                     mipmap ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR);
    if (mipmap) gl.generateMipmap(gl.TEXTURE_2D);
    return texture;
  }

  /* ------------------------------------------------------------------ *
   * Public factory
   * ------------------------------------------------------------------ */
  function create(gl, program, mapName) {
    const previousFlip = gl.getParameter(gl.UNPACK_FLIP_Y_WEBGL);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);

    const wind = uploadTexture(gl, WIND_SAMPLES, 1, buildWindPixels(), false);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const tracer = uploadTexture(gl, 1024, 512, buildTracerPixels(1024, 512), true);

    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, previousFlip);

    const vortexA = new Float32Array(MAX_VORTICES * 4);
    const vortexB = new Float32Array(MAX_VORTICES * 4);
    const list = VORTICES[mapName] || VORTICES.cassini;
    list.slice(0, MAX_VORTICES).forEach(function (vortex, index) {
      vortexA[index * 4 + 0] = vortex.u;
      vortexA[index * 4 + 1] = vortex.v;
      vortexA[index * 4 + 2] = vortex.rx;
      vortexA[index * 4 + 3] = (vortex.twist || 0.6) * (vortex.spin || 1) * CONFIG.VORTEX_SPIN;
      vortexB[index * 4 + 0] = vortex.ry;
      vortexB[index * 4 + 1] = vortex.period;
    });

    const location = function (name) { return gl.getUniformLocation(program, name); };
    const locations = {
      wind: location('u_wind'),
      tracer: location('u_tracer'),
      flowTime: location('u_flowTime'),
      live: location('u_live'),
      turbulence: location('u_turbulence'),
      contrast: location('u_contrast'),
      tracerSpeed: location('u_tracerSpeed'),
      vortexA: location('u_vortexA[0]') || location('u_vortexA'),
      vortexB: location('u_vortexB[0]') || location('u_vortexB'),
    };

    gl.useProgram(program);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, wind);
    gl.activeTexture(gl.TEXTURE2);
    gl.bindTexture(gl.TEXTURE_2D, tracer);
    gl.activeTexture(gl.TEXTURE0);
    gl.uniform1i(locations.wind, 1);
    gl.uniform1i(locations.tracer, 2);
    gl.uniform1f(locations.turbulence, CONFIG.TURBULENCE);
    gl.uniform1f(locations.contrast, CONFIG.CONTRAST);
    gl.uniform1f(locations.tracerSpeed, CONFIG.TRACER_SPEED);
    gl.uniform4fv(locations.vortexA, vortexA);
    gl.uniform4fv(locations.vortexB, vortexB);

    let live = CONFIG.LIVE_WEATHER ? 1 : 0;
    gl.uniform1f(locations.live, live);
    gl.uniform1f(locations.flowTime, 0);

    return {
      config: CONFIG,
      get live() { return live > 0.5; },
      setLive(value) {
        const next = value ? 1 : 0;
        if (next !== live) {
          live = next;
          gl.uniform1f(locations.live, live);
        }
        return live > 0.5;
      },
      setTime(seconds) {
        gl.uniform1f(locations.flowTime, seconds);
      },
    };
  }

  return { CONFIG: CONFIG, GLSL: GLSL, create: create, PROFILE: PROFILE };
})();
