# 木星 4K 动态壁纸

首次克隆项目后，先按下文“获取贴图”下载素材并生成播放纹理。完成后双击 `scripts/start_wallpaper.cmd` 启动，双击 `scripts/stop_wallpaper.cmd` 停止；改过脚本或贴图后双击 `scripts/restart_wallpaper.cmd` 重启（先停止再启动，确保加载的是新文件）。双击 `scripts/preview_rotation.cmd` 在浏览器中观看 30 秒一周的加速预览；当前桌面壁纸 5 分 57 秒一周，可在 `js/settings.js` 的 `rotation.periodSeconds` 里调整。程序把本地 Chrome/Edge WebGL 画面放到 Windows 桌面图标后面；素材准备完成后，播放不依赖联网。

默认使用卡西尼纹理。切换到哈勃版本时，先停止当前壁纸，再双击 `scripts/start_wallpaper_hubble.cmd`。

需要更高像素数的全球图时，先停止当前壁纸，再双击 `scripts/start_wallpaper_8k.cmd`。它采用 Cassini＋Juno 合成地图；原始发布文件为 14400×7200，运行时使用 8192×4096 的版本，以减少显卡内存占用。原版卡西尼图的色彩反差更鲜明，建议分别试用后选择喜欢的效果。

当前屏幕为 2560×1440。木星按至少 3840×2160 的场景坐标计算，但只为木星周围分配画布像素；其余区域由静态黑色页面背景填充。画面按屏幕比例缩小显示，屏幕硬件本身的物理像素数不会因此变成 4K。

## 开关实时大气

实时气流默认开启（`js/settings.js` 的 `atmosphere.live: true`）。下面三种方式都不用改代码：

1. **Ctrl+Alt+J**：壁纸运行中随时按，立即切换，不必重启。按下后画面顶部会出现约 2 秒的「实时模拟 已开启 / 已关闭」提示，确认当前状态。当前选择写入 `runtime/.live-weather.json`，下次启动沿用。
2. **双击 `scripts/toggle_weather.cmd`**：效果相同，适合用鼠标操作；若壁纸没在运行，它只改保存的设置。
3. **双击 `scripts/start_wallpaper_static.cmd`**：以关闭实时大气的刚性自转模式启动，球体、光照和转动次数照旧。

加速预览窗口里按 `L` 也能切换，左下角状态栏会显示“实时大气开/关”。URL 参数 `?live=0` / `?live=1` 可临时覆盖设置，便于做对比截图。

## 现成方案调研

动手前先检索了 GitHub 与图形学资料，看有没有“木星实时大气模拟”能直接拿来用。结论是**没有可作为本项目渲染层基础的现成代码**：

- [Eluvade/cosmos](https://github.com/Eluvade/cosmos)：TypeScript/WebGL 程序化天体库，气态行星用分带噪声与颜色渐变，只有 `time` 驱动的贴图动画，没有速度场或平流；可以借鉴着色器组织，不能当动力学基础。
- [THRASTRO/thrastro-shaders](https://github.com/THRASTRO/thrastro-shaders)：THREE.js 的行星/大气/环着色器集合，适合参考球面与临边处理，同样不含大气流动。
- [huazhige/Ge-et-al-water-Jupiter](https://github.com/huazhige/Ge-et-al-water-Jupiter)、[JupiRSW](https://github.com/Adrien-Cb/JupiRSW)、[2021.JupiterPolarVortex](https://github.com/chengcli/2021.JupiterPolarVortex)：C++/Python 的深大气或浅水环流模式，做的是长时间积分的科研实验，输出不了 60 帧/秒的桌面壁纸。
- SIGGRAPH 2015 的 [Wrangling a Gas Giant for Jupiter Ascending](https://history.siggraph.org/wp-content/uploads/2022/10/2015-Talks-Keip_Wrangling-a-Gas-Giant-for-Jupiter-Ascending.pdf)：电影里气态行星的做法（预先解算速度场，再做 Timeless Advection），思路可借，代码不公开。

因此实现路线是：**保留原有单文件 WebGL2 管线与 NASA 贴图，只替换纹理采样点的算法**，把“整图刚性自转”换成“实测急流剖面 + 解析涡旋 + 旋度噪声示踪场”的位移，也就是实时图形学里成熟的域扭曲、旋度噪声与按纬度分层平流三件事。全部是时间的纯函数，不需要反馈缓冲，所以长时间运行不会累积模糊或漂移。

风速与涡旋参数取自公开观测：赤道区被 ±7° 的东向急流夹住、赤道本身是局部极小；24°N 是木星最快的东向急流（1979 年约 180 m/s、1995 年约 140 m/s，后续加速期可超过 170 m/s）；大红斑位于 22.5°S，东西向约 1.6 万公里。参考 [Ingersoll et al. 2004, ch. 6](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)、[Porco et al. 2003](https://www.science.org/doi/10.1126/science.1080506)、[Sankar et al. 2021](https://arxiv.org/abs/2106.07809) 与 [BAA 木星喷流表](https://britastro.org/jupiter/reference/jup_jets/ref_jets.htm)。`js/atmosphere.js` 里的剖面是按这些锚点手工拟合的近似曲线，**不是逐点数字化数据**，只服务于视觉动效。

完整的检索记录、逐个仓库的结论与数据出处见 `jupiter-atmosphere-research.md`。[`demo_live_weather.gif`](previews/demo_live_weather.gif) 是 8 帧演示（约 100 秒模拟时间），[`preview_live_weather_4k.png`](previews/preview_live_weather_4k.png) 是 3840×2160 的实时大气整帧。

## 获取贴图

`assets/` 已加入 `.gitignore`，GitHub 仓库不包含原始图片或生成的播放纹理。请从以下来源下载**原始素材**，放入项目的 `assets/` 目录，并保持所示文件名：

- `PIA07782_Cassini.tif`：[NASA/JPL 卡西尼全球图 TIFF 直接下载](https://assets.science.nasa.gov/content/dam/science/psd/photojournal/pia/pia07/pia07782/PIA07782.tif)（约 19 MB；[作品说明页](https://science.nasa.gov/photojournal/cassinis-best-maps-of-jupiter-cylindrical-map/)）。
- `Hubble_Jupiter_color_global_map_2015a.tif`：[NASA SVS 哈勃 2015 全球图 TIFF 直接下载](https://svs.gsfc.nasa.gov/vis/a010000/a012000/a012021/Hubble_Jupiter_color_global_map_2015a.tif)（约 19 MB；[作品说明页](https://svs.gsfc.nasa.gov/12021/)）。
- `jupiter_cassini_juno_14400.png`：[行星学会 Cassini＋Juno 合成图 PNG 直接下载](https://planetary.s3.amazonaws.com/assets/images/5-jupiter/2018/jupiter_map_css_plus_juno_bj.png)（约 100 MB；[作品说明与署名](https://www.planetary.org/space-images/merged-cassini-and-juno)）。

在项目目录打开 PowerShell，可按下面的命令一次下载并生成所需的三个播放纹理。`python/prepare_textures.py` 依赖 Python 的 Pillow 和 NumPy；已安装时可跳过安装命令。

```powershell
New-Item -ItemType Directory -Force .\assets | Out-Null
Invoke-WebRequest 'https://assets.science.nasa.gov/content/dam/science/psd/photojournal/pia/pia07/pia07782/PIA07782.tif' -OutFile '.\assets\PIA07782_Cassini.tif'
Invoke-WebRequest 'https://svs.gsfc.nasa.gov/vis/a010000/a012000/a012021/Hubble_Jupiter_color_global_map_2015a.tif' -OutFile '.\assets\Hubble_Jupiter_color_global_map_2015a.tif'
Invoke-WebRequest 'https://planetary.s3.amazonaws.com/assets/images/5-jupiter/2018/jupiter_map_css_plus_juno_bj.png' -OutFile '.\assets\jupiter_cassini_juno_14400.png'
python -m pip install Pillow numpy
python python\prepare_textures.py
```

运行后会生成 `jupiter_cassini_2000.png`、`jupiter_hubble_2015.png` 和 `jupiter_cassini_juno_8k.png`。只下载卡西尼和哈勃图时，脚本也能生成前两张播放纹理；缺少合成图时不要使用 `scripts/start_wallpaper_8k.cmd`。

## 代码架构

### 目录结构

```text
jupiter-wallpaper/
├─ index.html             页面骨架：canvas、两行文字、按依赖顺序加载 6 个脚本
├─ README.md              本文件
├─ css/
│  └─ wallpaper.css       覆盖层样式（计数文字、状态行、开关提示）
├─ js/                    浏览器端
│  ├─ settings.js         全部可调参数（贴图/场景/自转/大气/交互）
│  ├─ atmosphere.js       大气模型：风速剖面、涡旋表、GLSL 位移函数、两张查表纹理
│  ├─ scene.js            WebGL2 渲染：球体反投影、光照、底图上传、draw()
│  ├─ rotation.js         自转相位 +「已自转 N 次」计数 + 与宿主的读写
│  ├─ live-mode.js        实时模拟开关：轮询 /live、POST、顶部提示、键盘 L
│  └─ wallpaper.js        入口编排：URL 参数 → 三个模块 → 帧调度
├─ python/                Python 端（全部无第三方依赖）
│  ├─ wallpaper_host.py   入口编排：启动流程、命令行、停止清理
│  ├─ host_win32.py       Win32：桌面层、窗口嵌入与尺寸校正、Chrome、热键
│  ├─ host_server.py      本机 HTTP：页面白名单、计数、播放状态、实时开关
│  ├─ host_common.py      路径、日志、两份 JSON 状态
│  ├─ prepare_textures.py NASA TIFF → 浏览器可用 PNG
│  ├─ render_preview.py   无头 Chrome 渲染单帧预览
│  ├─ preview_rotation.py 打开加速预览窗口
│  └─ analyze_vortices.py 从贴图量出大红斑/白卵坐标
├─ scripts/               双击运行的批处理入口
│  ├─ start_wallpaper.cmd          启动（沿用上次的实时/静态设置）
│  ├─ start_wallpaper_static.cmd   以静态模式启动
│  ├─ start_wallpaper_hubble.cmd   哈勃贴图
│  ├─ start_wallpaper_8k.cmd       Cassini＋Juno 合成图
│  ├─ stop_wallpaper.cmd           停止
│  ├─ restart_wallpaper.cmd        重启（改完代码用）
│  ├─ toggle_weather.cmd           切换实时模拟
│  └─ preview_rotation.cmd         加速预览
├─ assets/                贴图与生成的播放纹理（已 gitignore）
├─ docs/
│  └─ jupiter-atmosphere-research.md   调研记录与数据出处
├─ previews/              渲染出的预览图与演示 GIF（PNG 已 gitignore）
└─ runtime/               运行期产物：Chrome 配置、窗口状态、计数、开关、日志（已 gitignore）
```

### 浏览器端：一条从像素到贴图的链

```text
index.html
  ├─ js/settings.js        所有数值与开关，不含逻辑
  ├─ js/atmosphere.js      风场数据 + GLSL 片段（window.JupiterAtmosphere.GLSL）
  ├─ js/scene.js           把 GLSL 拼进片元着色器，建程序、建纹理、draw()
  ├─ js/rotation.js        相位与计数，不碰 DOM
  ├─ js/live-mode.js       开关状态，写进 scene.live
  └─ js/wallpaper.js       把上面几件事接起来
        │
        ├─ 每帧   scene.draw(turn)
        │          片元着色器：屏幕像素 → 扁球体求交 → 经纬度 → uv
        │            ├─ u_live = 0：直接采样底图（刚性自转）
        │            └─ u_live = 1：jupiterAtmosphere(uv, t) 位移后再采样
        └─ 每 250 ms / 1 s：轮询开关与播放状态，暂停时也检查相位
```

依赖是单向的：`settings → atmosphere → scene → live-mode → wallpaper`；`rotation` 只通过自己的 HTTP 接口与宿主通信。没有打包器，也没有 ES module，每个文件把一个对象挂到 `window` 上，加载顺序就是 `index.html` 里的顺序。

### 每个文件只负责一件事

| 文件 | 负责 | 不该出现的内容 |
|---|---|---|
| `js/settings.js` | 所有数值、贴图文件名、开关默认值 | 任何逻辑 |
| `js/atmosphere.js` | 风场/涡旋/噪声数据、GLSL、生成查表纹理 | 画布、DOM、时间 |
| `js/scene.js` | WebGL 状态、着色器装配、纹理上传、`draw()` | 自转相位、计数、提示文字 |
| `js/rotation.js` | 由时间算相位、判断跨圈、读写计数 | DOM、WebGL |
| `js/live-mode.js` | 轮询/POST 开关、顶部提示、键盘 `L` | 着色器、计数 |
| `js/wallpaper.js` | URL 参数、模块装配、帧调度、状态文字 | 具体算法 |
| `python/host_win32.py` | 桌面层、窗口嵌入与尺寸校正、Chrome 路径、全局热键 | HTTP、命令行 |
| `python/host_server.py` | 白名单静态文件 + 状态接口 | 窗口操作 |
| `python/host_common.py` | 路径、日志、JSON 读写 | ctypes、HTTP |
| `python/wallpaper_host.py` | 命令行解析、启动流程、停止清理 | 具体实现细节 |

### 宿主端的五个本机接口

| 接口 | 方向 | 用途 |
|---|---|---|
| `GET /rotation-count` | 页面 ← 宿主 | 启动时读历史圈数 |
| `POST /rotation-count` | 页面 → 宿主 | 转完一圈后上报，宿主去重后落盘 |
| `GET /playback` | 页面 ← 宿主 | 前台窗口遮住 95% 屏幕时暂停绘制 |
| `GET /live` | 页面 ← 宿主 | 每 250 ms 轮询开关 |
| `POST /live` | 页面/脚本/热键 → 宿主 | 切换实时模拟并写入 `runtime/.live-weather.json` |

### 按一次 Ctrl+Alt+J 发生了什么

1. `host_win32.poll_hotkey()` 从线程消息队列取到 `WM_HOTKEY`；
2. `host_server.set_live()` 改内存变量、写 `runtime/.live-weather.json`、记一行日志、返回结果；
3. 页面 250 ms 内轮询 `/live` 发现变化，`live-mode.js` 调 `scene.setLive()`；
4. `js/atmosphere.js` 把 `u_live` uniform 改成 0 或 1，下一帧生效；
5. `live-mode.js` 在画面顶部显示「实时模拟 已开启/已关闭」1.9 秒。

### 想改什么，去哪里

| 想改的东西 | 位置 |
|---|---|
| 自转快慢 | `js/settings.js` → `rotation.periodSeconds` |
| 木星大小、倾角、光照 | `js/settings.js` → `scene.*` |
| 默认是否实时、流速、对比、涡旋幅度、湍流 | `js/settings.js` → `atmosphere.*` |
| 换贴图或起始经度 | `js/settings.js` → `maps.*` |
| 风速剖面 | `js/atmosphere.js` → `PROFILE` |
| 大红斑/白卵位置 | `js/atmosphere.js` → `VORTICES`（用 `python/analyze_vortices.py` 量，再用 `?mark=` 核对） |
| 着色器算法 | `js/scene.js` 的 `fragmentShader()`、`js/atmosphere.js` 的 `GLSL` |
| 命令行与启动流程 | `python/wallpaper_host.py` |
| HTTP 接口 | `python/host_server.py` |

## 关键参数在哪里

以下参数集中在 `js/settings.js`；着色器内部的常数在 `js/scene.js` 的 `fragmentShader()`。改完双击 `scripts/restart_wallpaper.cmd` 生效。

- **旋转速度**：`rotation.periodSeconds`，默认 `357`（5 分 57 秒一周，比真实自转快 100 倍）。改成 `35730` 就是真实的 9 小时 55 分 30 秒。`rotation.demoPeriodSeconds`（默认 30）只控制加速预览。
- **画面刷新**：`js/wallpaper.js` 的 `frameInterval()`。开启实时模拟时按屏幕刷新率绘制，关闭时按自转速度取 17～500 毫秒的间隔省电；浏览器限制后台动画时由 200 毫秒的保险定时器补帧。
- **转动次数**：`js/rotation.js` 的 `observe()`。比较本次与上次的相位，只有从一周末端越过初始位置才加 1，不用“经过时间 ÷ 周期”的商。画面被遮挡暂停时也每秒检查一次，避免漏计。计数由 `python/host_server.py` 写入 `runtime/rotation-count.json`，旧版 `.rotation-count.json` 会自动迁移。
- **木星大小**：`scene.planetRadius`，默认 `0.72`，单位是画面高度的一半；过大可能超出屏幕。
- **扁率**：`scene.polarRatio`，默认 `66854 / 71492`，物理值。
- **画面倾斜**：`scene.tilt`，默认 `0.0541052` 弧度（约 3.1°）。
- **最低场景尺寸**：`scene.minWidth` / `scene.minHeight`，默认 3840×2160。提高会增加显卡负担，并不会提高屏幕的物理分辨率。
- **贴图与起始经度**：`maps.<名字>.file` 与 `maps.<名字>.phase`（0.36 / 0.645 / 0.83）。后者是构图值，不对应此刻的天文经度。
- **光照方向**：`scene.sun` 三个分量决定远处太阳方向；`scene.ambient` 与 `scene.diffuse` 控制明暗对比。
- **纹理清晰度**：`scene.mipBias`，默认 `-0.5`。`js/scene.js` 用 `textureGrad` 从**未位移**的 `uv` 求导数并按 `2^mipBias` 缩放，所以云带被拉扯时 mipmap 不会突然变糊。

### 实时大气参数（`js/settings.js` → `atmosphere`）

- `live`：默认是否开启；运行中请用 Ctrl+Alt+J 或 `scripts/toggle_weather.cmd`。
- `tracerSpeed`：示踪场流速倍率，默认 2.5。它和自转速度是“观感搭配”关系：把自转调慢 10 倍，这里也调小 10 倍即可保持同样的相对速度；0 则只剩涡旋与云带扭动。
- `contrast`：示踪场带来的明暗起伏强度。0 关闭、0.5 自然、1.0 以上会像电视雪花。
- `vortexSpin`：涡旋扭转幅度倍率，1.0 约等于大红斑核心与周围云领来回扭转 ±31°。
- `turbulence`：云带边缘被拉扯的强度，0.6 温和、1.5 剧烈。

风速剖面 `PROFILE` 与涡旋表 `VORTICES` 在 `js/atmosphere.js`：`PROFILE` 单位 `[纬度, 米/秒]`，正值为向东；`VORTICES` 是每张贴图的大红斑/白卵位置、椭圆半径与扭转周期，单位是贴图 uv。位置可用 `python/analyze_vortices.py` 重新量测，再用 `?mark=u,v` 在画面上打点核对。

## 全球图片怎样贴到球面上

NASA 的全球图是把木星表面按经纬度展开成一张长方形图片：横向跨越一整圈经度，纵向从北极到南极。程序将这张 PNG 作为 WebGL 纹理加载，**没有**用网页图片标签直接盖在圆形上，也没有把平面图片简单裁成圆形。

`js/scene.js` 的片元着色器对画布中的每个像素做一次反向映射：

1. 用 `gl_FragCoord` 把屏幕像素换成以木星中心为原点的坐标；根据 `R` 和 `POLAR_RATIO` 判断它是否落在可见的扁球体轮廓内。轮廓之外输出黑色。
2. 对轮廓内的像素，计算它在球体朝向观众这一面的深度 `z`，得到对应的三维表面位置，再求纬度 `latitude` 与经度 `longitude`。NASA Cassini 图使用行星心纬度；合成图和哈勃图按行星面纬度采样。
3. 把经纬度转换为纹理坐标 `uv`：横坐标由经度除以 `2π` 得到，纵坐标由纬度映射到 0～1。纹理采样器的 `GL_REPEAT` 让经度在图片左右边界循环，保留连续的纹理坐标以避免接缝处错误的 mipmap 层级；加载图片时的 `UNPACK_FLIP_Y_WEBGL` 负责使图片南北方向与 WebGL 坐标一致。
4. `textureGrad` 读取对应位置的云带颜色；开启实时大气时，先用 `jupiterAtmosphere()` 按气流把 `uv` 位移到新的采样点。自转时逐渐改变采样经度（`u_rotation`），因此全球图绕球面移动，木星轮廓保持不变。
5. 根据表面法线与模拟太阳方向计算明暗，并在轮廓边缘做抗锯齿和轻微临边效果，形成有体积感的木星。

这种做法相当于从三维扁球体表面反查二维全球图。贴图的清晰度受 NASA 原图分辨率限制；4K 渲染缓冲可使轮廓和画面输出更细腻，但不能凭空增加云层细节。

## 科学依据与素材

- 默认木星纹理：NASA/JPL/Cassini 的 [PIA07782 全球图](https://science.nasa.gov/photojournal/cassinis-best-maps-of-jupiter-cylindrical-map/)，原始 TIFF 为 3601×1801。NASA 指出它是详细的全球彩色图，颜色接近肉眼所见。`assets/jupiter_cassini_2000.png` 是基于原图制作的播放纹理。
- 可选纹理：NASA Goddard / STScI 的 [Hubble 2015 global map](https://svs.gsfc.nasa.gov/12021/)，原始 TIFF 为 3600×1800。`assets/jupiter_hubble_2015.png` 是基于原图制作的播放纹理。
- 高清可选纹理：[行星学会的 Cassini＋Juno 全球合成图](https://www.planetary.org/space-images/merged-cassini-and-juno)，由 Björn Jónsson 制作，原图 14400×7200，采用等距圆柱投影。程序保留原图 `assets/jupiter_cassini_juno_14400.png`，播放时读取缩至 8192×4096 的 `assets/jupiter_cassini_juno_8k.png`。图像署名：NASA / JPL-Caltech / SSI / Southwest Research Institute / Malin Space Science Systems / ASI / INAF / JIRAM / Björn Jónsson；按[知识共享署名 3.0 许可](https://creativecommons.org/licenses/by/3.0/)使用。合成图将不同年代的 Cassini 云带与 Juno 极区结合，**不代表同一时刻拍摄的木星**。
- 自转：System III 约 9 小时 55 分 30 秒。参考 [NASA 木星事实页](https://science.nasa.gov/jupiter/jupiter-facts/) 和 [JPL publication](https://assets.science.nasa.gov/content/dam/science/missions/europa-clipper/files/161_Grid2_JPL_Pub_14-8.pdf)。
- 自转方向：北方朝上时，云层特征由左向右移动，参考 [NASA/JPL 九帧旋转序列](https://www.jpl.nasa.gov/images/pia02825-nine-frames-as-jupiter-turns/)。
- 形状：NASA [Jupiter Fact Sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/jupiterfact.html) 的赤道半径 71,492 km、极半径 66,854 km。

卡西尼默认纹理拍于 2000 年、哈勃可选纹理拍于 2015 年；云层和大红斑会随时间变化。开启实时模拟（`js/atmosphere.js`）时，整张纹理不再按同一角速度转动：各条带按实测急流剪切，大红斑和白卵处叠加旋转涡旋，因此不同纬度的云带流速不同；剪切与涡旋都是有界振荡，不会随时间累积，长跑也不会把照片拧成花。关闭时退回刚性自转。哈勃图的极区缺测，着色器只在极端纬度用最近观测行延伸。太阳照明方向和起始经度是用于壁纸构图的设定，不代表当前时刻的真实木星朝向。14400×7200 是合成图文件尺寸，并不意味着每个区域都含有同等像素级的原始观测细节；本机 2560×1440 屏幕上，木星直径约 1000 物理像素，更大的贴图改善会受到显示尺寸限制。

为了减轻原版卡西尼与哈勃全球贴图的首尾拼接线，它们的播放用 PNG 在左右两侧各 64 像素范围内做了平滑过渡；原始 TIFF 文件保留在 `assets/` 目录。预览 PNG 可由 `python python\render_preview.py cassini`、`python python\render_preview.py hubble` 或 `python python\render_preview.py merged` 重新生成。

`python/render_preview.py` 的完整参数是 `python python\render_preview.py [cassini|hubble|merged] [phase] [live|static] [flow秒] [附加查询] [宽x高]`：

- 第二个参数指定测试经度，例如 `cassini 0` 用于检查背面接缝。
- 第三个参数 `static` 渲染关闭实时大气的对照帧，`live`（默认）渲染实时帧。
- 第四个参数 `flow` 把大气冻结在某一秒，便于对比同一自转角度下气流的变化。
- 第五个参数是附加查询串，例如 `"turn=0.9912"` 冻结自转角度、`"mark=0.3688,0.3792"` 在贴图坐标处点一个绿点核对涡旋位置。
- 第六个参数是窗口尺寸，例如 `1600x900`，默认 `3840x2160`。

例如生成一张 1600×900、把大红斑转到正中、大气冻结在第 45 秒的图：`python python\render_preview.py cassini 0.36 live 45 "turn=0.9912" 1600x900`。`demo_live_weather.gif` 是用同样参数渲染 8 帧拼成的演示动画，可以看到云带缓慢剪切、大红斑内部来回扭转。
