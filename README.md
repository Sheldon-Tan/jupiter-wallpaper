# 木星 4K 动态壁纸

首次克隆项目后，先按下文“获取贴图”下载素材并生成播放纹理。完成后双击 `start_wallpaper.cmd` 启动，双击 `stop_wallpaper.cmd` 停止。双击 `preview_rotation.cmd` 在浏览器中观看 30 秒一周的加速预览；当前桌面壁纸约 5 分 57 秒一周，可在 `wallpaper.js` 中调整。程序把本地 Chrome/Edge WebGL 画面放到 Windows 桌面图标后面；素材准备完成后，播放不依赖联网。

默认使用卡西尼纹理。切换到哈勃版本时，先停止当前壁纸，再双击 `start_wallpaper_hubble.cmd`。

需要更高像素数的全球图时，先停止当前壁纸，再双击 `start_wallpaper_8k.cmd`。它采用 Cassini＋Juno 合成地图；原始发布文件为 14400×7200，运行时使用 8192×4096 的版本，以减少显卡内存占用。原版卡西尼图的色彩反差更鲜明，建议分别试用后选择喜欢的效果。

当前屏幕为 2560×1440。木星按至少 3840×2160 的场景坐标计算，但只为木星周围分配画布像素；其余区域由静态黑色页面背景填充。画面按屏幕比例缩小显示，屏幕硬件本身的物理像素数不会因此变成 4K。

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
启动脚本（start_wallpaper*.cmd）
  └─ wallpaper_host.py → 本地 HTTP 服务 → Chrome/Edge 应用窗口
                                      └─ index.html → wallpaper.js → WebGL2 画面
  └─ Windows WorkerW 桌面层：把浏览器窗口放到桌面图标后面
停止脚本（stop_wallpaper.cmd）→ wallpaper_host.py stop
```

- `index.html`：木星画布、黑色页面背景及底部转动次数文字，加载 `wallpaper.js`。
- `wallpaper.js`：创建只包围木星的 WebGL2 画布、加载本地 NASA 纹理，在片元着色器中计算木星轮廓、经纬度、光照和自转；每次只重绘这块画布。
- `wallpaper_host.py`：启动仅供本机访问的 HTTP 服务及浏览器，把浏览器窗口嵌入 Windows 桌面层，并处理启动、停止、屏幕尺寸和计数保存。前台窗口覆盖至少 95% 屏幕时通知页面暂停绘制。
- `prepare_textures.py`：从原始 TIFF 生成播放用 PNG，柔化全球图的左右拼接边界；另将 14400×7200 合成图缩至 8192×4096。运行时只读取播放用 PNG，原始文件保留作素材。
- `render_preview.py`：生成静态预览图；`preview_rotation.py` 与 `preview_rotation.cmd`：打开 30 秒转一周的加速预览。

## 关键参数在哪里

以下参数均在 `wallpaper.js` 中。修改后停止并重新启动壁纸即可看到效果；要维持科学比例与自转速度，请保留标明为物理值的参数。

- **旋转速度**：搜索 `periodMs`。当前桌面值 `(9 * 3600 + 55 * 60 + 30) * 10`，约 5 分 57 秒一周；若要恢复真实自转速度，改为 `* 1000`，即 9 小时 55 分 30 秒一周。`demo ? 30000` 只控制加速预览。`u_rotation` 控制贴图的当前角度；`frameIntervalMs` 根据画面移动速度自动选择约 17～500 毫秒的刷新间隔。快速旋转时优先跟随屏幕刷新，浏览器限制后台动画时由定时器接管。全屏应用遮挡桌面时暂停绘制，再次显示桌面时按当前时间恢复。
- **转动次数**：搜索 `previousTurn` 和 `completedTurns`。每次绘制比较当前角度与上一次绘制的角度；只有看到角度从一周末端越过初始位置，数字才加 1，不用“经过时间 ÷ 周期”的商作为计数。暂停或长时间没有绘制后重新取角度基准，不推算期间未观察到的越界。桌面计数由 `wallpaper_host.py` 写入 `.rotation-count.json`，重启后继续累计；该本地文件已加入 `.gitignore`。30 秒加速预览不修改桌面计数。
- **木星大小**：搜索 `const float R = 0.720`。`R` 是赤道半径，以画面高度的一半为单位；目前赤道直径约为画面高度的 72%。增大 `R` 会放大木星，过大可能超出屏幕。
- **木星位置**：搜索 `p.x -= 0.30` 和 `p.y -= 0.015`。这两项把木星移到画面偏右、稍偏上的位置，为左侧桌面图标留出空间；数值单位同样是画面高度的一半。
- **扁率**：搜索 `POLAR_RATIO = 66854.0 / 71492.0`。这是木星极半径与赤道半径之比，决定球体略扁的外形，属于物理值。
- **画面倾斜**：搜索 `const float a = 0.0541052`。单位为弧度，约 3.1°；这是构图用的屏幕倾角。
- **最低场景尺寸**：搜索 `targetWidth` 和 `targetHeight`。完整场景坐标分别至少为 3840 和 2160 像素，同时考虑实际窗口尺寸与设备像素比；实际画布只占木星周围的矩形。提高数值会增加显卡负担，并不能提高屏幕的物理分辨率。
- **贴图和初始朝向**：启动 URL 中 `?map=cassini` / `?map=hubble` / `?map=merged` 选择纹理；`u_initial_phase` 的 `0.36` / `0.645` / `0.83` 控制三张图各自的起始可见经度，便于展示大红斑。它们是构图值，不对应此刻的天文经度。
- **纹理清晰度**：`texture(u_map, uv, -0.5)` 给 mipmap 采样一个轻微的清晰度偏置，减少过早使用低分辨率层造成的柔化；数值过低可能出现闪烁或锯齿。
- **光照**：搜索 `vec3 sun = normalize(vec3(-0.48, 0.23, 0.85))`。三个分量决定模拟远处太阳的入射方向；改变它们会移动明暗交界。

## 全球图片怎样贴到球面上

NASA 的全球图是把木星表面按经纬度展开成一张长方形图片：横向跨越一整圈经度，纵向从北极到南极。程序将这张 PNG 作为 WebGL 纹理加载，**没有**用网页图片标签直接盖在圆形上，也没有把平面图片简单裁成圆形。

`wallpaper.js` 的片元着色器对画布中的每个像素做一次反向映射：

1. 用 `gl_FragCoord` 把屏幕像素换成以木星中心为原点的坐标；根据 `R` 和 `POLAR_RATIO` 判断它是否落在可见的扁球体轮廓内。轮廓之外输出黑色。
2. 对轮廓内的像素，计算它在球体朝向观众这一面的深度 `z`，得到对应的三维表面位置，再求纬度 `latitude` 与经度 `longitude`。NASA Cassini 图使用行星心纬度；合成图和哈勃图按行星面纬度采样。
3. 把经纬度转换为纹理坐标 `uv`：横坐标由经度除以 `2π` 得到，纵坐标由纬度映射到 0～1。纹理采样器的 `GL_REPEAT` 让经度在图片左右边界循环，保留连续的纹理坐标以避免接缝处错误的 mipmap 层级；加载图片时的 `UNPACK_FLIP_Y_WEBGL` 负责使图片南北方向与 WebGL 坐标一致。
4. `texture(u_map, uv)` 读取对应位置的云带颜色。自转时逐渐改变采样经度（`u_rotation`），因此全球图绕球面移动，木星轮廓保持不变。
5. 根据表面法线与模拟太阳方向计算明暗，并在轮廓边缘做抗锯齿和轻微临边效果，形成有体积感的木星。

这种做法相当于从三维扁球体表面反查二维全球图。贴图的清晰度受 NASA 原图分辨率限制；4K 渲染缓冲可使轮廓和画面输出更细腻，但不能凭空增加云层细节。

## 科学依据与素材

- 默认木星纹理：NASA/JPL/Cassini 的 [PIA07782 全球图](https://science.nasa.gov/photojournal/cassinis-best-maps-of-jupiter-cylindrical-map/)，原始 TIFF 为 3601×1801。NASA 指出它是详细的全球彩色图，颜色接近肉眼所见。`assets/jupiter_cassini_2000.png` 是基于原图制作的播放纹理。
- 可选纹理：NASA Goddard / STScI 的 [Hubble 2015 global map](https://svs.gsfc.nasa.gov/12021/)，原始 TIFF 为 3600×1800。`assets/jupiter_hubble_2015.png` 是基于原图制作的播放纹理。
- 高清可选纹理：[行星学会的 Cassini＋Juno 全球合成图](https://www.planetary.org/space-images/merged-cassini-and-juno)，由 Björn Jónsson 制作，原图 14400×7200，采用等距圆柱投影。程序保留原图 `assets/jupiter_cassini_juno_14400.png`，播放时读取缩至 8192×4096 的 `assets/jupiter_cassini_juno_8k.png`。图像署名：NASA / JPL-Caltech / SSI / Southwest Research Institute / Malin Space Science Systems / ASI / INAF / JIRAM / Björn Jónsson；按[知识共享署名 3.0 许可](https://creativecommons.org/licenses/by/3.0/)使用。合成图将不同年代的 Cassini 云带与 Juno 极区结合，**不代表同一时刻拍摄的木星**。
- 自转：System III 约 9 小时 55 分 30 秒。参考 [NASA 木星事实页](https://science.nasa.gov/jupiter/jupiter-facts/) 和 [JPL publication](https://assets.science.nasa.gov/content/dam/science/missions/europa-clipper/files/161_Grid2_JPL_Pub_14-8.pdf)。
- 自转方向：北方朝上时，云层特征由左向右移动，参考 [NASA/JPL 九帧旋转序列](https://www.jpl.nasa.gov/images/pia02825-nine-frames-as-jupiter-turns/)。
- 形状：NASA [Jupiter Fact Sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/jupiterfact.html) 的赤道半径 71,492 km、极半径 66,854 km。

卡西尼默认纹理拍于 2000 年、哈勃可选纹理拍于 2015 年；云层和大红斑会随时间变化。壁纸按统一角速度转动整张纹理，未模拟不同纬度的喷流和风暴形变。哈勃图的极区缺测，着色器只在极端纬度用最近观测行延伸。太阳照明方向和起始经度是用于壁纸构图的设定，不代表当前时刻的真实木星朝向。14400×7200 是合成图文件尺寸，并不意味着每个区域都含有同等像素级的原始观测细节；本机 2560×1440 屏幕上，木星直径约 1000 物理像素，更大的贴图改善会受到显示尺寸限制。

为了减轻原版卡西尼与哈勃全球贴图的首尾拼接线，它们的播放用 PNG 在左右两侧各 64 像素范围内做了平滑过渡；原始 TIFF 文件保留在 `assets/` 目录。预览 PNG 可由 `python render_preview.py cassini`、`python render_preview.py hubble` 或 `python render_preview.py merged` 重新生成；可选的第二个参数指定测试经度，例如 `python render_preview.py cassini 0` 用于检查背面接缝。
