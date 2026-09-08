import {
  Texture,
  sRGBEncoding,
  CanvasTexture,
  Component,
  Tweening,
  WebGLRenderer,
  OrthographicCamera,
  MeshBasicMaterial,
  Scene,
  Primitives,
  InputEvents,
  Viewer,
  inspectProperty,
} from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
import { events } from "./../state/events.js";
var mB = Object.defineProperty,
  gB = Object.getOwnPropertyDescriptor,
  vB = (t, n, r, s) => {
    for (var h = s > 1 ? void 0 : s ? gB(n, r) : n, l = t.length - 1, g; l >= 0; l--)
      (g = t[l]) && (h = (s ? g(n, r, h) : g(h)) || h);
    return (s && h && mB(n, r, h), h);
  };
const _B = `
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="708" height="223" viewBox="0 0 708 223" fill="none">
<path d="M155.839 93.2234C140.396 89.3748 113.977 87.8351 92.3308 86.6804C80.7716 85.7822 70.6909 85.2051 64.4207 84.307C51.3763 82.5107 51.0537 69.6805 51.9542 63.1376C53.4395 54.4771 57.9019 46.4582 83.9974 43.4431C109.515 40.4281 164.428 50.628 179.22 53.2582C181.874 53.8355 183.36 53.2582 183.938 50.8846C185.423 41.3262 188.655 15.9867 188.655 15.9867C188.978 12.9717 187.493 10.919 184.522 10.0208C163.46 3.47748 120.113 -1.59041 84.2595 0.462399C57.25 1.93784 40.973 6.10765 27.5992 14.5113C5.95933 28.2395 -0.31087 48.2544 0.0117124 67.6275C0.334295 87.6423 8.3451 107.593 22.2363 117.794C35.2875 126.774 55.4422 128.506 80.7044 130.046C102.344 131.265 128.185 133.318 138.588 136.589C149.892 140.182 151.639 149.099 151.054 156.283C149.892 173.283 131.74 178.993 97.3712 178.993C68.621 178.993 47.2365 174.245 18.1704 170.332C14.9379 169.755 12.8075 170.332 12.5454 173.348L7.51176 210.041C7.18246 212.993 8.99698 215.43 11.0602 215.687C41.9407 221.332 73.0834 222.551 98.601 222.872C115.201 222.872 145.759 221.653 163.588 213.891C189.106 202.536 200.994 183.484 203.064 165.842C204.227 157.182 205.712 139.284 200.416 127.673C193.823 111.763 182.257 100.409 155.839 93.2234ZM457.273 3.99071L411.278 3.99071C409.208 3.99071 407.723 5.4661 407.723 7.26229L407.723 110.801C407.723 133.767 408.885 152.306 397.649 165.136C386.983 177.646 373.616 179.763 354.295 179.763C334.725 179.763 321.674 177.646 310.692 165.136C299.382 152.306 299.711 133.831 300.289 110.801L300.612 97.3938L300.612 7.26229C300.612 5.4661 299.126 3.99071 297.057 3.99071L251.384 3.99071C249.576 3.99071 248.152 5.4661 248.152 7.26229L248.152 110.801C248.152 148.136 250.222 179.121 271.284 200.034C291.761 220.306 317.541 223 354.362 223C390.861 223 415.478 221.204 436.54 200.612C457.017 180.019 460.243 148.072 460.243 110.801L460.243 7.26229C460.243 5.53026 459.02 3.99071 457.273 3.99071ZM704.384 3.99071L503.852 3.99071C501.789 3.99071 500.297 5.78688 500.297 7.58306L500.297 44.2771C500.297 46.3941 501.789 48.1261 503.852 48.1261L645.009 48.1261L639.458 58.2619C639.458 58.2619 573.886 168.664 550.432 213.441C549.524 215.559 550.432 218.83 552.824 218.83L604.182 218.83C606.252 218.83 609.8 218.253 610.708 216.457C638.873 168.408 682.482 91.4278 705.93 46.3941C706.837 44.2771 708 40.7489 708 36.2583L708 7.58306C708 5.78688 706.515 3.99071 704.384 3.99071Z"   fill="#424242" >
</path>
</svg>
`,
  yB = `
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="720.9970703125" height="115.619140625" viewBox="0 0 720.9970703125 115.619140625" fill="none">
<path d="M718.183 4.7692L694.916 4.7692C693.911 4.7692 693.099 5.54187 693.099 6.50771L693.099 111.013C693.099 111.947 693.911 112.752 694.916 112.752L718.183 112.752C719.154 112.752 719.997 111.979 719.997 111.013L719.997 6.50771C719.997 5.54187 719.188 4.7692 718.183 4.7692ZM646.922 12.6892C637.459 4.02868 622.228 2.96628 609.914 2.96628C594.002 2.96628 583.858 6.31456 577.703 9.40532L573.425 9.40532C567.431 6.15361 556.802 2.96628 540.176 2.96628C527.861 2.96628 512.728 3.86773 503.427 11.5302C495.714 17.8726 493.934 26.3721 493.934 43.7573L493.934 110.916C493.934 111.85 494.743 112.655 495.748 112.655L519.015 112.655C520.02 112.655 520.829 111.882 520.829 110.916L520.829 110.691C520.829 110.691 520.829 68.2258 520.829 55.6375C520.829 45.6568 520.441 35.2579 522.612 31.3946C524.328 28.3682 526.988 25.0199 539.626 25.0199C554.695 25.0199 558.258 26.0502 560.625 32.6179C561.174 34.1633 561.467 36.3847 561.596 39.0892C561.596 42.341 561.596 48.007 561.596 61.4003L561.596 110.949C561.596 111.882 562.408 112.687 563.413 112.687L563.443 112.687L586.68 112.687L586.71 112.687C587.715 112.687 588.527 111.914 588.527 110.949L588.527 61.4003C588.527 48.0394 588.527 42.373 588.527 39.0892C588.655 36.3847 588.945 34.1954 589.498 32.6179C591.865 26.0502 595.428 25.0199 610.497 25.0199C623.135 25.0199 625.791 28.4004 627.511 31.3946C629.712 35.2579 629.294 45.6568 629.294 55.6375C629.294 68.2258 629.294 110.691 629.294 110.691L629.294 110.916C629.294 111.85 630.103 112.655 631.108 112.655L654.375 112.655C655.38 112.655 656.189 111.882 656.189 110.916L656.189 47.8462C656.158 29.817 655.541 20.577 646.922 12.6892ZM177.909 4.7692L154.642 4.7692C153.637 4.7692 152.827 5.54187 152.827 6.50771L152.827 111.013C152.827 111.947 153.637 112.752 154.642 112.752L177.909 112.752C178.881 112.752 179.724 111.979 179.724 111.013L179.724 6.50771C179.724 5.54187 178.914 4.7692 177.909 4.7692ZM80.0757 57.859L121.426 7.47359C122.333 6.37896 121.523 4.73697 120.097 4.73697L90.2834 4.73697C89.5704 4.73697 88.8901 5.05898 88.4687 5.63849L61.1503 41.2783L34.4806 5.67065C34.0592 5.09114 33.3786 4.7692 32.6656 4.7692L2.75503 4.7692C1.32915 4.7692 0.551443 6.37896 1.42641 7.47359L43.2949 58.7925L1.39397 110.047C0.519006 111.142 1.32915 112.752 2.75503 112.752L32.6332 112.752C33.3462 112.752 34.0592 112.398 34.4806 111.818L62.3818 76.3067L88.825 111.818C89.2464 112.398 89.927 112.719 90.64 112.719L120.162 112.719C121.587 112.719 122.365 111.11 121.49 110.015L80.0757 57.859ZM312.88 19.096C302.121 4.51163 282.678 0.100887 262.521 1.16332C242.073 2.25798 227.814 6.50771 224.185 7.85989C221.917 8.69698 222.208 10.6287 222.176 11.7555C222.078 15.619 221.787 24.6658 221.819 28.7224C221.819 30.4931 224.055 31.3302 225.935 30.6863C233.388 28.0785 247.161 23.9253 258.243 23.056C270.201 22.0902 286.858 23.3458 291.362 30.0102C293.631 33.3906 294.02 39.7008 294.344 45.0132C286.89 44.2404 275.386 42.9525 263.947 43.5641C255.392 44.0149 239.027 45.1096 229.402 50.1644C221.56 54.2853 216.958 57.9878 214.528 64.9417C212.551 70.5436 212.032 75.888 212.648 81.3612C214.074 93.853 218.481 100.067 224.444 104.413C233.842 111.27 245.702 114.877 270.234 114.329C302.866 113.621 311.454 103.254 315.796 95.8812C323.153 83.3254 321.889 63.5253 321.662 51.3555C321.5 46.3651 320.722 29.7526 312.88 19.096ZM291.978 85.6756C288.9 92.0499 277.363 92.9515 270.849 93.2734C258.827 93.821 249.526 93.0482 243.791 90.2793C239.999 88.4442 236.92 84.2909 236.693 79.4617C236.467 75.3732 237.05 72.9582 238.832 70.4472C242.883 64.6841 254.387 63.2998 265.729 62.8814C273.636 62.5914 285.918 63.493 294.603 64.5553C294.441 73.1194 293.76 81.9407 291.978 85.6756ZM405.79 2.7731C389.359 2.7731 372.864 4.8336 362.461 14.8785C352.058 24.9555 348.04 40.0872 348.04 58.6317C348.04 77.2083 351.637 92.0499 362.04 102.127C372.443 112.172 389.325 114.619 405.756 114.619C422.217 114.619 438.584 112.558 448.987 102.481C459.387 92.4043 463.503 77.1759 463.503 58.6317C463.503 40.0872 459.873 25.3097 449.439 15.2326C439.069 5.18773 422.217 2.7731 405.79 2.7731ZM431.488 86.2228C425.524 92.9194 414.7 94.1106 405.79 94.1106C396.877 94.1106 386.086 92.9194 380.122 86.2551C374.159 79.5585 373.737 70.4792 373.737 58.6637C373.737 46.8482 374.129 38.0266 380.092 31.3302C386.052 24.6336 395.646 23.4424 405.79 23.4424C415.93 23.4424 425.524 24.6014 431.488 31.3302C437.448 38.0266 437.839 46.8482 437.839 58.6637C437.839 70.4792 437.448 79.5261 431.488 86.2228Z" stroke="rgba(222, 222, 222, 1)" stroke-width="2"   >
</path>
</svg>
`;
function sm(t, n = !1) {
  const r = new Image(),
    s = new Texture(r);
  return (
    (s.encoding = sRGBEncoding),
    (r.src = n ? t : "data:image/svg+xml," + encodeURIComponent(t)),
    (r.onload = () => {
      s.needsUpdate = !0;
    }),
    s
  );
}
function Cv(t) {
  const n = new CanvasTexture(t);
  return ((n.encoding = sRGBEncoding), n);
}
class PhotoComposer extends Component {
  constructor() {
    super(...arguments);
    B(this, "_qrcode");
    B(this, "_camera");
    B(this, "_material");
    B(this, "_frontScene");
    B(this, "_frontRenderer");
    B(this, "_hiddenObjects", []);
    B(this, "_isSaving", !1);
    B(this, "_canvasTexture");
    B(this, "_qrcodeTexture");
    B(this, "_carMesh");
  }
  show() {
    ((this.enabled = !0),
      (this._material.opacity = 0),
      Tweening.TweenManager.KillTweensOf(this._material),
      Tweening.TweenManager.Tween(this._material)
        .to(
          {
            opacity: 1,
          },
          1,
        )
        .easing(Tweening.Easing.Cubic.InOut)
        .start());
  }
  hide() {
    this.enabled = !1;
  }
  screenshot() {
    (this._frontRenderer === void 0 &&
      ((this._frontRenderer = new WebGLRenderer()),
      this._frontRenderer.setPixelRatio(window.devicePixelRatio),
      (this._frontRenderer.outputEncoding = this.viewer.renderer.outputEncoding)),
      (this._isSaving = !0),
      this.viewer.render(0),
      (this._canvasTexture.needsUpdate = !0),
      (this._isSaving = !1));
    const r = this.viewer.size;
    (this._hiddenObjects.forEach((h) => (h.visible = !0)),
      this._frontRenderer.setSize(r.width, r.height),
      this._frontRenderer.render(this._frontScene, this._camera),
      this._hiddenObjects.forEach((h) => (h.visible = !1)));
    const s = document.getElementById("screenshot-img");
    if (s) {
      const h = (1228.8 * r.width) / 1920,
        l = (h * r.height) / r.width;
      ((s.src = this._frontRenderer.domElement.toDataURL("image/png")),
        (s.width = h),
        (s.height = l));
    }
  }
  onEnable() {
    events.on(events.SCREENSHOT, this.screenshot, this);
  }
  onDisable() {
    events.off(events.SCREENSHOT, this.screenshot, this);
  }
  onLoad() {
    const r = this.viewer.size;
    ((this._camera = new OrthographicCamera(
      -r.width / 2,
      r.width / 2,
      r.height / 2,
      -r.height / 2,
      0,
      1,
    )),
      (this._material = new MeshBasicMaterial({
        transparent: !0,
        toneMapped: !1,
        depthWrite: !1,
        depthTest: !1,
        map: new Texture(),
      })),
      (this.viewer.renderer.sortObjects = !1),
      (this._frontScene = new Scene()));
    const s = (this._carMesh = new Primitives.Plane(1, 1));
    ((s.material = this._material),
      (s.localUniforms.map = this._canvasTexture = Cv(this.viewer.renderer.domElement)),
      this._frontScene.add(s),
      this._hiddenObjects.push(s));
    const h = new Primitives.Plane(500, (500 * 228) / 718);
    ((h.material = this._material), (h.localUniforms.map = sm(_B)), this._frontScene.add(h));
    const g = new Primitives.Plane(550, (550 * 118) / 729);
    ((g.material = this._material), (g.localUniforms.map = sm(yB)), this._frontScene.add(g));
    (this._hiddenObjects.forEach((m) => (m.visible = !1)),
      this._updateLayout(),
      this.viewer.on(InputEvents.RESIZE, this._onResize, this),
      this.viewer.on(Viewer.RENDER_AFTER, this._onAfterRender, this));
  }
  onDestroy() {
    this.viewer.targetOff(this);
  }
  _onAfterRender() {
    this.enabled && !this._isSaving && this.viewer.renderer.render(this._frontScene, this._camera);
  }
  _onResize(r, s) {
    ((this._camera.left = -r / 2),
      (this._camera.right = r / 2),
      (this._camera.top = s / 2),
      (this._camera.bottom = -s / 2),
      this._camera.updateProjectionMatrix(),
      this._updateLayout(),
      this._canvasTexture.dispose(),
      (this._canvasTexture = this._carMesh.localUniforms.map =
        Cv(this.viewer.renderer.domElement)));
  }
  _updateLayout() {
    const { width, height } = this.viewer.size;
    const scale = width / 1920;
    const children = this._frontScene.children;
    children.forEach((item) => item.scale.set(scale, scale, scale));
    children[0].scale.set(width, height, 1);
    children[1].position.set(width * (-0.5 + 0.2), height * (0.5 - 0.2), 0);
    children[2].position.set(width * (0.5 - 0.23), height * (-0.5 + 0.15), 0);
  }
}
vB([inspectProperty()], PhotoComposer.prototype, "screenshot", 1);
export { mB, gB, vB, _B, yB, sm, Cv, PhotoComposer };
