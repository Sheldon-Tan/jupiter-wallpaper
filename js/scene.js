/* WebGL2 场景：只负责“把木星画到 canvas 上”。
 *
 * 职责边界：
 *   - 画布尺寸与定位（只为木星周围分配像素，其余交给黑色背景）
 *   - 着色器装配（球体反投影 + 光照 + 注入 atmosphere.js 的位移函数）
 *   - 底图纹理上传；大气查表纹理由 atmosphere.js 自己上传
 *   - draw(turn) 画一帧；不计算时间、不认识 DOM 文字
 *
 * 用法：JupiterScene.create({ canvas, mapName, phase, mark })
 */
window.JupiterScene = (function () {
  'use strict';

  const VERTEX_SHADER = `#version 300 es
    precision highp float;
    void main() {
      vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
      gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
    }`;

  // 没有 atmosphere.js 时的兜底：声明同名 uniform，位移函数原样返回。
  const FALLBACK_ATMOSPHERE_GLSL = `
    uniform float u_flowTime;
    uniform float u_live;
    uniform float u_contrast;
    vec3 jupiterAtmosphere(vec2 uv, float t) { return vec3(uv, 0.5); }`;

  function normalizedSun(sceneSettings) {
    const [x, y, z] = sceneSettings.sun;
    const length = Math.hypot(x, y, z) || 1;
    return [x / length, y / length, z / length].map(value => value.toFixed(6));
  }

  function fragmentShader(atmosphereGLSL, sceneSettings) {
    const sun = normalizedSun(sceneSettings);
    // 用 2^bias 缩放导数，等价于 texture() 的 LOD 偏置。
    const mipScale = Math.pow(2, sceneSettings.mipBias).toFixed(8);
    const limb = sceneSettings.limbColor.map(value => value.toFixed(4)).join(', ');
    return `#version 300 es
    precision highp float;
    uniform vec2 u_resolution;
    uniform vec2 u_origin;
    uniform sampler2D u_map;
    uniform float u_rotation;
    uniform float u_initial_phase;
    uniform float u_polar_limit;
    uniform float u_planetographic;
    uniform vec2 u_mark;
    ${atmosphereGLSL}
    out vec4 outColor;

    const float PI = 3.141592653589793;
    const float POLAR_RATIO = ${sceneSettings.polarRatio.toFixed(8)};
    const float TILT = ${sceneSettings.tilt.toFixed(8)};
    const float PLANET_RADIUS = ${sceneSettings.planetRadius.toFixed(6)};
    const float MIP_SCALE = ${mipScale};
    const vec3 SUN_DIR = vec3(${sun.join(', ')});
    const vec3 LIMB_COLOR = vec3(${limb});
    const float AMBIENT = ${sceneSettings.ambient.toFixed(4)};
    const float DIFFUSE = ${sceneSettings.diffuse.toFixed(4)};
    const float LIMB_POWER = ${sceneSettings.limbPower.toFixed(4)};
    const float LIMB_STRENGTH = ${sceneSettings.limbStrength.toFixed(4)};

    void main() {
      vec2 p = (gl_FragCoord.xy + u_origin - 0.5 * u_resolution) / (0.5 * u_resolution.y);
      // 视在北极倾角；木星真实转轴相对轨道约 3.1°。
      vec2 q = vec2(cos(TILT) * p.x + sin(TILT) * p.y,
                    -sin(TILT) * p.x + cos(TILT) * p.y);
      // 正交视线与扁球体求交：shape = 1 就是可见边缘。
      float shape = dot(q / vec2(PLANET_RADIUS, PLANET_RADIUS * POLAR_RATIO),
                        q / vec2(PLANET_RADIUS, PLANET_RADIUS * POLAR_RATIO));
      if (shape > 1.003) {
        outColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
      }

      float z = PLANET_RADIUS * sqrt(max(0.0, 1.0 - shape));
      vec3 normal = normalize(vec3(q.x, q.y / (POLAR_RATIO * POLAR_RATIO), z));
      float horizontal = length(vec2(q.x, z));
      float planetocentric = atan(q.y, horizontal);
      float planetographic = atan(q.y / (POLAR_RATIO * POLAR_RATIO), horizontal);
      float latitude = mix(planetocentric, planetographic, u_planetographic);
      float longitude = atan(q.x, z);
      // 北极朝上时，自转让云层特征自左向右移动。
      vec2 uv = vec2(u_initial_phase + longitude / (2.0 * PI) - u_rotation,
                     0.5 + latitude / PI);
      // GL_REPEAT 负责经度环绕；保持坐标不折回，mipmap 导数才正确。
      uv.y = clamp(uv.y, u_polar_limit, 1.0 - u_polar_limit);

      // 实时大气只让微弱的示踪层流动；NASA 底图坐标始终保持原样。
      float cloud = 0.5;
      vec2 deck = uv;
      if (u_live > 0.5) {
        vec3 atmosphere = jupiterAtmosphere(uv, u_flowTime);
        deck = atmosphere.xy;
        cloud = atmosphere.z;
      }
      // 底图坐标和导数都来自原始 uv，长期运行不会拉伸照片。
      vec2 dX = dFdx(uv) * MIP_SCALE;
      vec2 dY = dFdy(uv) * MIP_SCALE;
      vec3 clouds = textureGrad(u_map, deck, dX, dY).rgb;
      // 示踪场的明暗起伏；关闭实时大气时恒为 1.0。
      clouds *= 1.0 + (cloud - 0.5) * u_contrast;
      // 标定用绿点（?mark=u,v）：核对涡旋位置。
      if (u_mark.x >= 0.0) {
        vec2 gap = deck - u_mark;
        gap.x -= floor(gap.x + 0.5);
        if (length(gap * vec2(1.0, 2.0)) < 0.006) clouds = vec3(0.1, 1.0, 0.2);
      }

      // 单一远处太阳：漫反射 + 极细的临边雾。
      float incidence = max(dot(normal, SUN_DIR), 0.0);
      float lit = AMBIENT + DIFFUSE * incidence;
      float limb = pow(1.0 - max(normal.z, 0.0), LIMB_POWER);
      vec3 planet = clouds * lit + LIMB_COLOR * limb * incidence * LIMB_STRENGTH;
      float aa = max(fwidth(shape), 0.001);
      float cover = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, shape);
      outColor = vec4(mix(vec3(0.0), planet, cover), 1.0);
    }`;
  }

  function compile(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(shader) || '着色器编译失败');
    }
    return shader;
  }

  function create(options) {
    const settings = window.JUPITER_SETTINGS;
    const sceneSettings = settings.scene;
    const map = settings.maps[options.mapName];
    const canvas = options.canvas;

    /* ---- 画布尺寸与定位 ------------------------------------------------ */
    const targetWidth = Math.max(sceneSettings.minWidth,
                                 Math.round(innerWidth * devicePixelRatio));
    const targetHeight = Math.max(sceneSettings.minHeight,
                                  Math.round(innerHeight * devicePixelRatio));
    const radius = Math.ceil(sceneSettings.planetRadius * targetHeight / 2 + 8);
    const centerX = targetWidth / 2;
    const centerY = targetHeight / 2;
    const left = Math.max(0, Math.floor(centerX - radius));
    const bottom = Math.max(0, Math.floor(centerY - radius));
    const right = Math.min(targetWidth, Math.ceil(centerX + radius));
    const top = Math.min(targetHeight, Math.ceil(centerY + radius));
    canvas.width = right - left;
    canvas.height = top - bottom;

    function position() {
      // 宿主脚本在页面加载后才把窗口放大；两轴用同一个缩放比例，保证球体不扁。
      const scale = innerHeight / targetHeight;
      canvas.style.left = `${innerWidth / 2 + (left - targetWidth / 2) * scale}px`;
      canvas.style.top = `${innerHeight / 2 - (top - targetHeight / 2) * scale}px`;
      canvas.style.width = `${canvas.width * scale}px`;
      canvas.style.height = `${canvas.height * scale}px`;
    }
    position();
    addEventListener('resize', position);

    /* ---- WebGL 上下文 -------------------------------------------------- */
    const gl = canvas.getContext('webgl2', {
      antialias: false, alpha: false, depth: false, stencil: false,
      powerPreference: 'high-performance', preserveDrawingBuffer: false,
    });
    if (!gl) throw new Error('无法启动 WebGL 2。请更新显卡驱动，或在 Chrome 中启用硬件加速。');

    /* ---- 着色器程序 ---------------------------------------------------- */
    const program = gl.createProgram();
    gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, VERTEX_SHADER));
    gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, fragmentShader(
      window.JupiterAtmosphere ? window.JupiterAtmosphere.GLSL : FALLBACK_ATMOSPHERE_GLSL,
      sceneSettings)));
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program) || '着色器链接失败');
    }
    gl.useProgram(program);
    gl.bindVertexArray(gl.createVertexArray());
    gl.viewport(0, 0, canvas.width, canvas.height);

    const uniform = name => gl.getUniformLocation(program, name);
    gl.uniform2f(uniform('u_resolution'), targetWidth, targetHeight);
    gl.uniform2f(uniform('u_origin'), left, bottom);
    gl.uniform1i(uniform('u_map'), 0);
    gl.uniform1f(uniform('u_initial_phase'),
                 options.phase !== null && options.phase !== undefined
                   ? options.phase : map.phase);
    gl.uniform1f(uniform('u_polar_limit'), map.polarLimit);
    gl.uniform1f(uniform('u_planetographic'), map.planetographic ? 1 : 0);
    gl.uniform2f(uniform('u_mark'),
                 options.mark ? options.mark.u : -1,
                 options.mark ? options.mark.v : -1);
    const rotationLocation = uniform('u_rotation');

    /* ---- 实时大气：查表、涡旋与 uniform 全部委托给模型 ------------------ */
    const atmosphere = window.JupiterAtmosphere
      ? window.JupiterAtmosphere.create(gl, program, options.mapName)
      : null;

    /* ---- 底图纹理 ------------------------------------------------------ */
    const mapTexture = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, mapTexture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    // 贴图是北在上方的图片，上传时翻转，使 v=0 对应南极。
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);

    const ready = new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        try {
          gl.bindTexture(gl.TEXTURE_2D, mapTexture);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB8, gl.RGB, gl.UNSIGNED_BYTE, image);
          gl.generateMipmap(gl.TEXTURE_2D);
          resolve();
        } catch (error) {
          reject(error);
        }
      };
      image.onerror = () => reject(new Error('NASA 木星纹理加载失败'));
      image.src = map.file;
    });
    ready.then(() => { window.jupiterReady = true; }, () => {});

    /* ---- 对外接口 ------------------------------------------------------ */
    return {
      ready,
      label: map.label,
      dimensions: { width: targetWidth, height: targetHeight },
      hasAtmosphere: !!atmosphere,
      get live() { return atmosphere ? atmosphere.live : false; },
      setLive(value) {
        return atmosphere ? atmosphere.setLive(value) : false;
      },
      setFlowTime(seconds) {
        if (atmosphere) atmosphere.setTime(seconds);
      },
      draw(turn) {
        gl.uniform1f(rotationLocation, turn);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      },
    };
  }

  return { create };
})();
