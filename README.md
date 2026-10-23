# 木星 4K 动态壁纸

首次克隆项目后，先按下文“获取贴图”下载素材并生成播放纹理。完成后双击 `start_wallpaper.cmd` 启动，双击 `stop_wallpaper.cmd` 停止；改过脚本或贴图后双击 `restart_wallpaper.cmd` 重启（先停止再启动，确保加载的是新文件）。双击 `preview_rotation.cmd` 在浏览器中观看 30 秒一周的加速预览；当前桌面壁纸约 36 秒一周，可在 `wallpaper.js` 中调整。程序把本地 Chrome/Edge WebGL 画面放到 Windows 桌面图标后面；素材准备完成后，播放不依赖联网。

默认使用卡西尼纹理。切换到哈勃版本时，先停止当前壁纸，再双击 `start_wallpaper_hubble.cmd`。

需要更高像素数的全球图时，先停止当前壁纸，再双击 `start_wallpaper_8k.cmd`。它采用 Cassini＋Juno 合成地图；原始发布文件为 14400×7200，运行时使用 8192×4096 的版本，以减少显卡内存占用。原版卡西尼图的色彩反差更鲜明，建议分别试用后选择喜欢的效果。

当前屏幕为 2560×1440。木星按至少 3840×2160 的场景坐标计算，但只为木星周围分配画布像素；其余区域由静态黑色页面背景填充。画面按屏幕比例缩小显示，屏幕硬件本身的物理像素数不会因此变成 4K。

## 开关实时大气

实时气流默认开启（`atmosphere.js` 顶部的 `LIVE_WEATHER: true`）。下面三种方式都不用改代码：

1. **Ctrl+Alt+J**：壁纸运行中随时按，立即切换，不必重启。按下后画面顶部会出现约 2 秒的「实时模拟 已开启 / 已关闭」提示，确认当前状态。当前选择写入 `.live-weather.json`，下次启动沿用。
2. **双击 `toggle_weather.cmd`**：效果相同，适合用鼠标操作；若壁纸没在运行，它只改保存的设置。
3. **双击 `start_wallpaper_static.cmd`**：以关闭实时大气的刚性自转模式启动，球体、光照和转动次数照旧。

加速预览窗口里按 `L` 也能切换，左下角状态栏会显示“实时大气开/关”。URL 参数 `?live=0` / `?live=1` 可临时覆盖设置，便于做对比截图。

## 现成方案调研

动手前先检索了 GitHub 与图形学资料，看有没有“木星实时大气模拟”能直接拿来用。结论是**没有可作为本项目渲染层基础的现成代码**：

- [Eluvade/cosmos](https://github.com/Eluvade/cosmos)：TypeScript/WebGL 程序化天体库，气态行星用分带噪声与颜色渐变，只有 `time` 驱动的贴图动画，没有速度场或平流；可以借鉴着色器组织，不能当动力学基础。
- [THRASTRO/thrastro-shaders](https://github.com/THRASTRO/thrastro-shaders)：THREE.js 的行星/大气/环着色器集合，适合参考球面与临边处理，同样不含大气流动。
- [huazhige/Ge-et-al-water-Jupiter](https://github.com/huazhige/Ge-et-al-water-Jupiter)、[JupiRSW](https://github.com/Adrien-Cb/JupiRSW)、[2021.JupiterPolarVortex](https://github.com/chengcli/2021.JupiterPolarVortex)：C++/Python 的深大气或浅水环流模式，做的是长时间积分的科研实验，输出不了 60 帧/秒的桌面壁纸。
- SIGGRAPH 2015 的 [Wrangling a Gas Giant for Jupiter Ascending](https://history.siggraph.org/wp-content/uploads/2022/10/2015-Talks-Keip_Wrangling-a-Gas-Giant-for-Jupiter-Ascending.pdf)：电影里气态行星的做法（预先解算速度场，再做 Timeless Advection），思路可借，代码不公开。

因此实现路线是：**保留原有单文件 WebGL2 管线与 NASA 贴图，只替换纹理采样点的算法**，把“整图刚性自转”换成“实测急流剖面 + 解析涡旋 + 旋度噪声示踪场”的位移，也就是实时图形学里成熟的域扭曲、旋度噪声与按纬度分层平流三件事。全部是时间的纯函数，不需要反馈缓冲，所以长时间运行不会累积模糊或漂移。

风速与涡旋参数取自公开观测：赤道区被 ±7° 的东向急流夹住、赤道本身是局部极小；24°N 是木星最快的东向急流（1979 年约 180 m/s、1995 年约 140 m/s，后续加速期可超过 170 m/s）；大红斑位于 22.5°S，东西向约 1.6 万公里。参考 [Ingersoll et al. 2004, ch. 6](https://lasp.colorado.edu/mop/files/2015/08/jupiter_ch6-1.pdf)、[Porco et al. 2003](https://www.science.org/doi/10.1126/science.1080506)、[Sankar et al. 2021](https://arxiv.org/abs/2106.07809) 与 [BAA 木星喷流表](https://britastro.org/jupiter/reference/jup_jets/ref_jets.htm)。`atmosphere.js` 里的剖面是按这些锚点手工拟合的近似曲线，**不是逐点数字化数据**，只服务于视觉动效。

完整的检索记录、逐个仓库的结论与数据出处见 `jupiter-atmosphere-research.md`。[`demo_live_weather.gif`](demo_live_weather.gif) 是 8 帧演示（约 100 秒模拟时间），[`preview_live_weather_4k.png`](preview_live_weather_4k.png) 是 3840×2160 的实时大气整帧。

## 获取贴图

`assets/` 已加入 `.gitignore`，GitHub 仓库不包含原始图片或生成的播放纹理。请从以下来源下载**原始素材**，放入项目的 `assets/` 目录，并保持所示文件名：

- `PIA07782_Cassini.tif`：[NASA/JPL 卡西尼全球图 TIFF 直接下载](https://assets.science.nasa.gov/content/dam/science/psd/photojournal/pia/pia07/pia07782/PIA07782.tif)（约 19 MB；[作品说明页](https://science.nasa.gov/photojournal/cassinis-best-maps-of-jupiter-cylindrical-map/)）。
- `Hubble_Jupiter_color_global_map_2015a.tif`：[NASA SVS 哈勃 2015 全球图 TIFF 直接下载](https://svs.gsfc.nasa.gov/vis/a010000/a012000/a012021/Hubble_Jupiter_color_global_map_2015a.tif)（约 19 MB；[作品说明页](https://svs.gsfc.nasa.gov/12021/)）。
- `jupiter_cassini_juno_14400.png`：[行星学会 Cassini＋Juno 合成图 PNG 直接下载](https://planetary.s3.amazonaws.com/assets/images/5-jupiter/2018/jupiter_map_css_plus_juno_bj.png)（约 100 MB；[作品说明与署名](https://www.planetary.org/space-images/merged-cassini-and-juno)）。

在项目目录打开 PowerShell，可按下面的命令一次下载并生成所需的三个播放纹理。`prepare_textures.py` 依赖 Python 的 Pillow 和 NumPy；已安装时可跳过安装命令。

```powershell
New-Item -ItemType Directory -Force .\assets | Out-Null
Invoke-WebRequest 'https://assets.science.nasa.gov/content/dam/science/psd/photojournal/pia/pia07/pia07782/PIA07782.tif' -OutFile '.\assets\PIA07782_Cassini.tif'
Invoke-WebRequest 'https://svs.gsfc.nasa.gov/vis/a010000/a012000/a012021/Hubble_Jupiter_color_global_map_2015a.tif' -OutFile '.\assets\Hubble_Jupiter_color_global_map_2015a.tif'
Invoke-WebRequest 'https://planetary.s3.amazonaws.com/assets/images/5-jupiter/2018/jupiter_map_css_plus_juno_bj.png' -OutFile '.\assets\jupiter_cassini_juno_14400.png'
python -m pip install Pillow numpy
python prepare_textures.py
```

运行后会生成 `jupiter_cassini_2000.png`、`jupiter_hubble_2015.png` 和 `jupiter_cassini_juno_8k.png`。只下载卡西尼和哈勃图时，脚本也能生成前两张播放纹理；缺少合成图时不要使用 `start_wallpaper_8k.cmd`。

## 代码架构

```text
NASA 全球图（assets/*.tif）与 Cassini＋Juno 合成图（assets/*.png）
  └─ prepare_textures.py → 可供浏览器读取的 PNG 纹理（assets/*.png）
启动脚本（start_wallpaper*.cmd、restart_wallpaper.cmd）
  └─ wallpaper_host.py → 本地 HTTP 服务 → Chrome/Edge 应用窗口
                                      └─ index.html → wallpaper.js → WebGL2 画面
                                                       └─ atmosphere.js → 气流位移与涡旋
  └─ Windows WorkerW 桌面层：把浏览器窗口放到桌面图标后面
停止脚本（stop_wallpaper.cmd）→ wallpaper_host.py stop
```

- `index.html`：木星画布、黑色页面背景及底部转动次数文字，加载 `wallpaper.js`。
- `wallpaper.js`：创建只包围木星的 WebGL2 画布、加载本地 NASA 纹理，在片元着色器中计算木星轮廓、经纬度、光照和自转；每次只重绘这块画布。
- `atmosphere.js`：实时大气。CPU 侧生成条带风速查表与旋度噪声示踪场，片元着色器据此把贴图采样点按急流位移，并叠加有界的涡旋扭转与明暗起伏；`toggle_weather.cmd` 或 Ctrl+Alt+J 可随时切回刚性自转。
- `wallpaper_host.py`：启动仅供本机访问的 HTTP 服务及浏览器，把浏览器窗口嵌入 Windows 桌面层，并按实际网页区域校正窗口边界，使黑色背景覆盖整个屏幕；同时处理启动、停止、屏幕尺寸和计数保存。前台窗口覆盖至少 95% 屏幕时通知页面暂停绘制。
- `prepare_textures.py`：从原始 TIFF 生成播放用 PNG，柔化全球图的左右拼接边界；另将 14400×7200 合成图缩至 8192×4096。运行时只读取播放用 PNG，原始文件保留作素材。
- `render_preview.py`：生成静态预览图；`preview_rotation.py` 与 `preview_rotation.cmd`：打开 30 秒转一周的加速预览。

## 关键参数在哪里

以下参数均在 `wallpaper.js` 中。修改后停止并重新启动壁纸即可看到效果；要维持科学比例与自转速度，请保留标明为物理值的参数。

- **旋转速度**：搜索 `periodMs`。当前桌面值 `(9 * 3600 + 55 * 60 + 30) * 1`，约 36 秒一周。这个数按毫秒解释，所以乘数每增大 10 倍，转一周就慢 10 倍：`* 10` 约 5 分 57 秒，`* 1000` 才是真实的 9 小时 55 分 30 秒。`demo ? 30000` 只控制加速预览。`u_rotation` 控制贴图的当前角度；`frameInterval()` 在开启实时大气时按屏幕刷新绘制，静止壁纸则按画面移动速度取约 17～500 毫秒的刷新间隔。浏览器限制后台动画时由定时器接管。全屏应用遮挡桌面时暂停绘制，再次显示桌面时按当前时间恢复。
- **转动次数**：搜索 `observeRotation`、`previousTurn` 和 `completedTurns`。比较本次与上次检查的旋转角度；角度从一周末端越过初始位置时，数字加 1，不用“经过时间 ÷ 周期”的商作为计数。绘制时会检查角度，画面暂停时也每秒检查一次，避免桌面被窗口遮挡时漏计。桌面计数由 `wallpaper_host.py` 写入项目根目录的 `rotation-count.json`，启动时先读取已有次数，再继续累计；旧版 `.rotation-count.json` 会自动迁移。计数文件已加入 `.gitignore`，30 秒加速预览也不修改桌面计数。
- **木星大小**：搜索 `const float R = 0.720`。`R` 是赤道半径，以画面高度的一半为单位；目前赤道直径约为画面高度的 72%。增大 `R` 会放大木星，过大可能超出屏幕。
- **木星位置**：搜索 `centerX`、`centerY`。两者目前分别为画面宽度和高度的一半，木星正对屏幕中心；画布裁剪区域也围绕同一中心计算。若日后需要移动木星，应同步调整画布中心和片元着色器中的表面坐标。
- **扁率**：搜索 `POLAR_RATIO = 66854.0 / 71492.0`。这是木星极半径与赤道半径之比，决定球体略扁的外形，属于物理值。
- **画面倾斜**：搜索 `const float a = 0.0541052`。单位为弧度，约 3.1°；这是构图用的屏幕倾角。
- **最低场景尺寸**：搜索 `targetWidth` 和 `targetHeight`。完整场景坐标分别至少为 3840 和 2160 像素，同时考虑实际窗口尺寸与设备像素比；实际画布只占木星周围的矩形。提高数值会增加显卡负担，并不能提高屏幕的物理分辨率。
- **贴图和初始朝向**：启动 URL 中 `?map=cassini` / `?map=hubble` / `?map=merged` 选择纹理；`u_initial_phase` 的 `0.36` / `0.645` / `0.83` 控制三张图各自的起始可见经度，便于展示大红斑。它们是构图值，不对应此刻的天文经度。
- **纹理清晰度**：`textureGrad(u_map, deck, dX, dY)` 用未被气流位移的 `uv` 求导数，再据此选择 mipmap 层；导数乘 `0.70710678` 相当于原来 `-0.5` 的清晰度偏置，减少过早使用低分辨率层造成的柔化，也保证实时大气拉扯云带时画面不发虚。
- **光照**：搜索 `vec3 sun = normalize(vec3(-0.48, 0.23, 0.85))`。三个分量决定模拟远处太阳的入射方向；改变它们会移动明暗交界。

### 实时大气参数（`atmosphere.js`）

`atmosphere.js` 顶部的 `CONFIG` 是给使用者调的，改完重启壁纸生效（运行中切换请用 Ctrl+Alt+J 或 `toggle_weather.cmd`）：

- `LIVE_WEATHER`：`true` 开启实时气流，`false` 退回刚性自转。
- `TRACER_SPEED`：示踪场的流动速度倍率。默认 2.5 与现在约 36 秒一周的自转速度相称；把自转调慢 10 倍时，把它也调小 10 倍即可保持同样的相对观感，0 则只剩涡旋与云带扭动。
- `CONTRAST`：示踪场带来的明暗起伏强度。0 关闭、0.5 自然、1.0 以上会像电视雪花。
- `VORTEX_SPIN`：涡旋扭转幅度倍率，1.0 约等于大红斑核心与周围云带来回扭转 ±31°。
- `TURBULENCE`：云带边缘被拉扯的强度，0.6 温和、1.5 剧烈。

`CONFIG` 下面的 `PROFILE` 是风速剖面，单位 `[纬度, 米/秒]`，正值为向东；`VORTICES` 是三张贴图各自的大红斑/白卵位置、椭圆半径与扭转周期，单位为贴图 uv。位置可用 `analyze_vortices.py` 重新量测，再用 `?mark=u,v` 在画面上打点核对。

## 全球图片怎样贴到球面上

NASA 的全球图是把木星表面按经纬度展开成一张长方形图片：横向跨越一整圈经度，纵向从北极到南极。程序将这张 PNG 作为 WebGL 纹理加载，**没有**用网页图片标签直接盖在圆形上，也没有把平面图片简单裁成圆形。

`wallpaper.js` 的片元着色器对画布中的每个像素做一次反向映射：

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

卡西尼默认纹理拍于 2000 年、哈勃可选纹理拍于 2015 年；云层和大红斑会随时间变化。开启实时大气（`atmosphere.js`）时，整张纹理不再按同一角速度转动：各条带按实测急流剪切，大红斑和白卵处叠加旋转涡旋，因此不同纬度的云带流速不同；剪切与涡旋都是有界振荡，不会随时间累积，长跑也不会把照片拧成花。关闭时退回刚性自转。哈勃图的极区缺测，着色器只在极端纬度用最近观测行延伸。太阳照明方向和起始经度是用于壁纸构图的设定，不代表当前时刻的真实木星朝向。14400×7200 是合成图文件尺寸，并不意味着每个区域都含有同等像素级的原始观测细节；本机 2560×1440 屏幕上，木星直径约 1000 物理像素，更大的贴图改善会受到显示尺寸限制。

为了减轻原版卡西尼与哈勃全球贴图的首尾拼接线，它们的播放用 PNG 在左右两侧各 64 像素范围内做了平滑过渡；原始 TIFF 文件保留在 `assets/` 目录。预览 PNG 可由 `python render_preview.py cassini`、`python render_preview.py hubble` 或 `python render_preview.py merged` 重新生成。

`render_preview.py` 的完整参数是 `python render_preview.py [cassini|hubble|merged] [phase] [live|static] [flow秒] [附加查询] [宽x高]`：

- 第二个参数指定测试经度，例如 `cassini 0` 用于检查背面接缝。
- 第三个参数 `static` 渲染关闭实时大气的对照帧，`live`（默认）渲染实时帧。
- 第四个参数 `flow` 把大气冻结在某一秒，便于对比同一自转角度下气流的变化。
- 第五个参数是附加查询串，例如 `"turn=0.9912"` 冻结自转角度、`"mark=0.3688,0.3792"` 在贴图坐标处点一个绿点核对涡旋位置。
- 第六个参数是窗口尺寸，例如 `1600x900`，默认 `3840x2160`。

例如生成一张 1600×900、把大红斑转到正中、大气冻结在第 45 秒的图：`python render_preview.py cassini 0.36 live 45 "turn=0.9912" 1600x900`。`demo_live_weather.gif` 是用同样参数渲染 8 帧拼成的演示动画，可以看到云带缓慢剪切、大红斑内部来回扭转。
