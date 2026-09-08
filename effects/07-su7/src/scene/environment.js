import shader1 from "../shaders/environment-01.glsl?raw";
import shader2 from "../shaders/environment-02.glsl?raw";
import {
  Component,
  ShaderMaterial,
  WebGLRenderTarget,
  LinearFilter,
  HalfFloatType,
  RGBAFormat,
  LinearEncoding,
  CubeUVReflectionMapping,
  Q3,
  inspectProperty,
  Tweening,
} from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
var VO = Object.defineProperty,
  WO = Object.getOwnPropertyDescriptor,
  uM = (t, n, r, s) => {
    for (var h = s > 1 ? void 0 : s ? WO(n, r) : n, l = t.length - 1, g; l >= 0; l--)
      (g = t[l]) && (h = (s ? g(n, r, h) : g(h)) || h);
    return (s && h && VO(n, r, h), h);
  };
const jO = shader1,
  XO = shader2;
class EnvironmentMixer extends Component {
  constructor(r) {
    super();
    B(this, "_envRT");
    B(this, "_mixMaterial");
    B(this, "_pmremGenerator");
    B(this, "_needsUpdate", !0);
    this._init = () => {
      const s = r.envMap0,
        h = r.envMap1;
      this._mixMaterial = new ShaderMaterial({
        vertexShader: jO,
        fragmentShader: XO,
        uniforms: {
          tEnv0: {
            value: s,
          },
          tEnv1: {
            value: h,
          },
          intensity: {
            value: 1,
          },
          weight: {
            value: 0,
          },
        },
      });
      const l = s.source.data;
      ((this._envRT = new WebGLRenderTarget(l.width, l.height, {
        magFilter: LinearFilter,
        minFilter: LinearFilter,
        generateMipmaps: !1,
        type: HalfFloatType,
        format: RGBAFormat,
        encoding: LinearEncoding,
        depthBuffer: !1,
      })),
        (this._envRT.texture.mapping = CubeUVReflectionMapping));
    };
  }
  get intensity() {
    return this._mixMaterial.uniforms.intensity.value;
  }
  set intensity(r) {
    this._mixMaterial.uniforms.intensity.value !== r &&
      ((this._mixMaterial.uniforms.intensity.value = r), (this._needsUpdate = !0));
  }
  get weight() {
    return this._mixMaterial.uniforms.weight.value;
  }
  set weight(r) {
    this._mixMaterial.uniforms.weight.value !== r &&
      ((this._mixMaterial.uniforms.weight.value = r), (this._needsUpdate = !0));
  }
  get envMap() {
    return this._envRT.texture;
  }
  onLoad() {
    this._init && this._init();
  }
  update() {
    this._needsUpdate &&
      ((this._needsUpdate = !1), Q3(this.viewer.renderer, this._envRT, this._mixMaterial));
  }
  onDestroy() {
    var r;
    (this._envRT.dispose(),
      this._mixMaterial.dispose(),
      (r = this._pmremGenerator) == null || r.dispose());
  }
}
uM(
  [
    inspectProperty({
      min: 0,
      max: 1,
      step: 0.01,
    }),
  ],
  EnvironmentMixer.prototype,
  "intensity",
  1,
);
uM(
  [
    inspectProperty({
      min: 0,
      max: 1,
      step: 0.01,
    }),
  ],
  EnvironmentMixer.prototype,
  "weight",
  1,
);
var U_ = ((t) => (
  (t[(t.dark = 0)] = "dark"),
  (t[(t.night = 1)] = "night"),
  (t[(t.light = 2)] = "light"),
  t
))(U_ || {});
class EnvironmentController extends Component {
  constructor(r, s) {
    super();
    B(this, "_dynamicEnv");
    this.onLoad = () => {
      ((this._dynamicEnv = this.viewer.addNode(
        new EnvironmentMixer({
          envMap0: r,
          envMap1: s,
        }),
      )),
        (this._dynamicEnv.intensity = 0),
        (this._dynamicEnv.weight = 0),
        (this.viewer.scene.environment = this._dynamicEnv.envMap));
    };
  }
  setState(r, s = 1, h = Tweening.Easing.Cubic.InOut, l = 1) {
    switch (r) {
      case 0:
        (Tweening.TweenManager.KillTweensOf(this._dynamicEnv),
          Tweening.TweenManager.Tween(this._dynamicEnv)
            .to(
              {
                intensity: 0,
                weight: 0,
              },
              s,
            )
            .easing(h)
            .start());
        break;
      case 1:
        (Tweening.TweenManager.KillTweensOf(this._dynamicEnv),
          Tweening.TweenManager.Tween(this._dynamicEnv)
            .to(
              {
                intensity: l,
                weight: 0,
              },
              s,
            )
            .easing(h)
            .start());
        break;
      case 2:
        (Tweening.TweenManager.KillTweensOf(this._dynamicEnv),
          Tweening.TweenManager.Tween(this._dynamicEnv)
            .to(
              {
                intensity: l,
                weight: 1,
              },
              s,
            )
            .easing(h)
            .start());
        break;
    }
  }
}
export { VO, WO, uM, jO, XO, EnvironmentMixer, U_, EnvironmentController };
