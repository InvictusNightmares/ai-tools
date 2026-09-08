# Xiaomi SU7 3D 展示源码

参考效果：[gamemcu.com/su7](https://gamemcu.com/su7/)，采集版本为资源 `1.0.5`、页面代码 `1.1.4`。

基于公开发布内容整理的可编辑源码工程，包含真实 3D 模型、原始贴图、着色器、相机轨迹、反射和 React 界面。页面作者/音频作者署名，以及拍照图片中的作者水印、推广二维码均已移除；原站统计脚本不包含在工程内。

## 开发

需要 Node.js 22 或更新版本。

```bash
cd /Users/invictus/Github/ai-tools/effects/07-su7
npm ci
npm run dev
```

打开 [http://127.0.0.1:8768](http://127.0.0.1:8768/)。直接编辑 `src/` 即可预览，不需要先构建。端口可通过 `npm run dev -- --port 9000` 修改。

```bash
npm run check   # 核对素材 SHA-256、大小和源码引用
npm run build   # 生成 dist/ 静态站点
npm run preview
```

构建预览地址为 [http://127.0.0.1:8769](http://127.0.0.1:8769/)。常规 `dist/` 版本支持部署到子目录，资源使用相对路径，需要通过 HTTP 服务打开。

## 单 HTML 离线版

```bash
npm run build:single
```

生成 [dist-single/su7.html](dist-single/su7.html)。只需复制这一个文件，使用支持 WebGL 的桌面浏览器直接打开，无需启动服务或联网。模型、贴图、HDR、图标、音频、CSS 和 JavaScript 全部内嵌，保留 3D 交互和拍照功能。手机端需使用能执行本地 HTML 的浏览器；文件管理器的预览模式不保证支持 WebGL。

构建脚本先校验 47 个素材，再生成单个普通脚本和内嵌素材表。运行时按需转换为 Blob URL，保留扩展名供模型和音频加载器识别。修改源码后重新执行上述命令即可。

## 交互

- SU7：开场镜头、展厅反射、拖动观察和按住触发的加速效果。
- 车身：车身比例与尺寸展示。
- 风阻：围绕车身流动的风阻曲线。
- 雷达：传感器点位、扫描体积和周围车辆。
- 定制：九种预设车漆、三种特殊涂装及自定义车漆。
- 自定义：色相、饱和度、明度、金属度、粗糙度五项调整。
- 拍照：生成当前车辆图片，保留 SU7 / Xiaomi 产品标志。
- 音频：背景音乐和点击反馈开关。

保留原站横屏展示策略：竖屏窗口中旋转场景，不改为上下滚动的手机页面。真机浏览器的自动播放限制仍由浏览器决定，首次手势后才可能开始播放音频。

## 修改位置

| 源码 | 内容 |
| --- | --- |
| `src/App.jsx`、`src/main.jsx` | React 入口和界面组成 |
| `src/ui/` | 加载、章节导航、文案、换色、五个材质滑杆、声音、拍照界面 |
| `src/styles.css` | 展开后的原站布局与样式 |
| `src/config/resources.js` | 素材路径、共享 uniform、车漆与涂装参数 |
| `src/state/events.js` | 场景状态和事件定义 |
| `src/scene/experience.js` | 资源初始化、五个章节、镜头与动画时序 |
| `src/scene/camera.js`、`orbit.js` | 弹性相机、拖拽、缩放和输入处理 |
| `src/scene/reflection.js` | 展厅地面平面反射 |
| `src/scene/materials.js`、`environment.js` | 车身材质、环境混合与灯光 |
| `src/scene/effects.js` | 尺寸、流线、扫描和传感器效果 |
| `src/scene/photo-composer.js` | 无作者水印的拍照合成 |
| `src/scene/audio.js` | 音频精灵与背景音乐 |
| `src/shaders/` | 独立 GLSL 着色器和注入片段 |
| `src/engine/` | 原站 xviewer 运行时与扩展过的 Three.js r150 源码 |
| `public/1.0.5/` | 本地模型、贴图、图标、HDR 和音频 |
| `asset-manifest.json` | 47 个素材的来源、大小和 SHA-256 |

## 源码说明

这是公开发布代码的源码重建，不是作者未公开的 Git 仓库、TypeScript 工程或建模工程。应用逻辑已拆成 ES 模块，React 界面恢复为 JSX，主要场景类、状态变量和 Three.js 类型恢复为可读名称。部分局部变量和内部导出标识仍保留发布时名称。

原站对 Three.js r150 的 MathUtils、Object3D、Vector3、Matrix3 和 WebGLRenderer 做过扩展，直接换成 npm 官方版本会丢失这些行为。因此保留展开后的引擎源码及原有延迟初始化顺序。`src/engine/modules/` 按相机、输入、加载器、材质、补间、渲染器等职责分文件；这里没有直接引用原站压缩 JS。

React 18.2、React DOM 18.2、Framer Motion 和 Vite 使用固定 npm 版本，由锁文件约束。界面动画库采用兼容的 Framer Motion 11.18.2；原站未暴露其精确版本，未声称逐帧一致。

所有当前展示所需的媒体资源均在本地。引擎保留通用加载器代码，其未使用的 Draco 解码器默认地址不参与这组模型的加载。

`dist/` 和 `dist-single/` 仅在构建时生成，两者及 `node_modules/` 已忽略。源码、素材和构建配置均保留，单文件版可重复生成。模型为原站发布的网格数据，不包含 Blender / Maya 建模源文件。

## 验证

见 [design-qa.md](design-qa.md) 中的浏览器检查记录和截图。构建与静态素材检查不能替代真机测试，手机视口验证是在桌面浏览器中完成的。

## 素材与第三方许可

模型、图片、字体、音频等素材的权利归原权利人所有。页面隐藏署名不改变素材权属。来源留在素材清单和本文档中，第三方库的许可保留在依赖包中；Three.js 的 MIT 许可见 [docs/THREE-LICENSE.txt](docs/THREE-LICENSE.txt)。
