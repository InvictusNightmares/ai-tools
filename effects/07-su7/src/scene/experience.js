import {
  VisibilityController,
  MovingSensor,
  DimensionsEffect,
  CurvatureEffect,
  WindEffect,
  LineCarEffect,
  SensorPoints,
  RadarEffect,
  TrafficEffect,
} from "./effects.js";
import { defineField as B } from "./../engine/fields.js";
import { resources, resourceConfig } from "./../config/resources.js";
import {
  Component,
  inspectProperty,
  PMREMGenerator,
  LinearEncoding,
  RepeatWrapping,
  NearestFilter,
  sRGBEncoding,
  J3,
  DataTexture,
  RGBAFormat,
  FloatType,
  MeshStandardMaterial,
  Color,
  dO,
  Euler,
  Vector3,
  K3,
  fO,
  Tweening,
} from "./../engine/index.js";
import { events, ShowState, ColorPanelState } from "./../state/events.js";
import { AudioController } from "./audio.js";
import { AA, UO, kO, NO, zO, GO, HO, Ag, FO, BO } from "./materials.js";
import { PhotoComposer } from "./photo-composer.js";
import { PlanarReflection } from "./reflection.js";
import { EnvironmentController, U_ } from "./environment.js";
import {
  TaillightController,
  HeadlightController,
  PointerEffects,
  WheelMotion,
} from "./lights-and-motion.js";
import { SpringCamera } from "./camera.js";
import { OrbitController } from "./orbit.js";
class LightbarController extends VisibilityController {
  constructor() {
    super(...arguments);
    B(this, "_lightMt", null);
  }
  onLoad() {
    const { materials: r } = resources.sm_car_lightbar.meshData;
    ((this._lightMt = r.lightbar_Baked),
      this.viewer.addNode(resources.sm_car_lightbar),
      (this.controller = new Proxy(
        {
          visibility: 1,
        },
        {
          set: (s, h, l) => ((s[h] = l), !0),
        },
      )),
      (this.controller.visibility = 0));
  }
  update(r) {
    this._lightMt && (this._lightMt.emissiveIntensity = 500 * this.controller.visibility + 1);
  }
}
var bB = Object.defineProperty,
  wB = Object.getOwnPropertyDescriptor,
  AB = (t, n, r, s) => {
    for (var h = s > 1 ? void 0 : s ? wB(n, r) : n, l = t.length - 1, g; l >= 0; l--)
      (g = t[l]) && (h = (s ? g(n, r, h) : g(h)) || h);
    return (s && h && bB(n, r, h), h);
  };
class SectionInspector extends Component {
  get state() {
    return events.currentShowingState;
  }
  set state(n) {
    events.emit(events.UPDATESHOWINGSTATE, n);
  }
}
AB(
  [
    inspectProperty({
      value: ShowState,
    }),
  ],
  SectionInspector.prototype,
  "state",
  1,
);
class Experience extends Component {
  constructor() {
    super(...arguments);
    B(this, "_environment");
    B(this, "_posterGenerator");
    B(this, "_envController");
    B(this, "_springCtr");
    B(this, "_carLightController");
    B(this, "_topLightController");
    B(this, "_carSpeedUpdate");
    B(this, "_bloom");
    B(this, "_projectionProbe");
    B(this, "_accessories");
  }
  start() {
    (console.log(resourceConfig.VERSION),
      this._preload().then(() => {
        (this._prepareScene(), this._createScene(), this._compileScene());
      }));
  }
  async _preload() {
    const r = new PMREMGenerator(this.viewer.renderer);
    return Promise.all([
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_car.glb"),
        })
        .then((s) => {
          resources.sm_car = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_startroom.raw.glb"),
        })
        .then((s) => {
          resources.sm_startroom = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_speedup.glb"),
        })
        .then((s) => {
          resources.sm_speedup = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_size.glb"),
        })
        .then((s) => {
          resources.sm_size = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_curvature.glb"),
        })
        .then((s) => {
          resources.sm_curvature = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_windspeed.glb"),
        })
        .then((s) => {
          resources.sm_windspeed = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_linecar.glb"),
        })
        .then((s) => {
          resources.sm_linecar = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_carradar.glb"),
        })
        .then((s) => {
          resources.sm_carradar = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_simplecar.glb"),
        })
        .then((s) => {
          resources.sm_simpleCar = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/mesh/sm_car_lightbar.glb"),
        })
        .then((s) => {
          resources.sm_car_lightbar = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_saLine.png"),
          flipY: !1,
          encoding: LinearEncoding,
          wrapS: RepeatWrapping,
          wrapT: RepeatWrapping,
          anisotropy: 4,
        })
        .then((s) => (resources.ut_saLine.value = s)),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_car_body_AO.raw.jpg"),
          flipY: !1,
          encoding: LinearEncoding,
          minFilter: NearestFilter,
          magFilter: NearestFilter,
        })
        .then((s) => (resources.ut_car_body_ao.value = s)),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_startroom_ao.raw.jpg"),
          flipY: !1,
          encoding: LinearEncoding,
        })
        .then((s) => {
          resources.ut_startroom_ao.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_startroom_light.raw.jpg"),
          flipY: !1,
          encoding: sRGBEncoding,
        })
        .then((s) => {
          resources.ut_startroom_light.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_floor_normal.webp"),
          flipY: !1,
          encoding: LinearEncoding,
          wrapS: RepeatWrapping,
          wrapT: RepeatWrapping,
        })
        .then((s) => {
          resources.ut_floor_normal.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_floor_roughness.jpg"),
          flipY: !1,
          encoding: LinearEncoding,
          wrapS: RepeatWrapping,
          wrapT: RepeatWrapping,
        })
        .then((s) => {
          resources.ut_floor_roughness.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_street.png"),
          flipY: !1,
          wrapS: RepeatWrapping,
          wrapT: RepeatWrapping,
        })
        .then((s) => {
          resources.ut_street.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_scar_matcap.png"),
          flipY: !1,
        })
        .then((s) => {
          resources.ut_scar_matcap.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_gm_car_body_bc.png"),
          flipY: !1,
        })
        .then((s) => {
          resources.ut_car_body_t_gm.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_gm02_car_body_bc.jpg"),
          flipY: !1,
          anisotropy: 4,
        })
        .then((s) => {
          resources.ut_car_body_t_gm2.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_gm02_car_window_bc.png"),
          flipY: !1,
        })
        .then((s) => {
          resources.ut_gm02_car_window_bc.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_gm02_car_window_roughness.jpg"),
          flipY: !1,
          minFilter: NearestFilter,
          magFilter: NearestFilter,
        })
        .then((s) => {
          resources.ut_gm02_car_window_roughness.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_gm02_floor_bc.png"),
          flipY: !1,
          anisotropy: 4,
        })
        .then((s) => {
          resources.ut_gm02_floor_bc.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_police_Car_body_BC.png"),
          flipY: !1,
          anisotropy: 4,
        })
        .then((s) => {
          resources.ut_police_Car_body_BC.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_police_floor_bc.jpg"),
          flipY: !1,
          anisotropy: 4,
        })
        .then((s) => {
          resources.ut_police_floor_bc.value = s;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_env_night.hdr"),
        })
        .then((s) => {
          resources.ut_env_night.value = r.fromEquirectangular(s).texture;
        }),
      this.viewer
        .loadAsset({
          url: resourceConfig.autoURL("res/texture/t_env_light.hdr"),
        })
        .then((s) => {
          resources.ut_env_light.value = r.fromEquirectangular(s).texture;
        }),
    ]);
  }
  _prepareScene() {
    const r = this.viewer;
    (r.addNode(AudioController),
      r.addNode(SectionInspector),
      (this._environment = r.addNode(
        new J3({
          scene: r.scene,
          layer: resources.LAYER_CAPTURE,
          resolution: 512,
        }),
      )),
      (this._environment.blurIntensity = 4.5),
      (resources.ut_cubeCapture = this._environment.cubeTexture),
      (resources.ut_blurCapture = this._environment.blurTexture));
    const s = new Float32Array(4);
    s.set([1, 1, 1, 1]);
    const h = new DataTexture(s, 1, 1, RGBAFormat, FloatType);
    ((h.needsUpdate = !0), (resources.ut_white.value = h));
    const l = new Float32Array(4);
    l.set([0, 0, 0, 1]);
    const g = new DataTexture(l, 1, 1, RGBAFormat, FloatType);
    ((g.needsUpdate = !0), (resources.ut_dark.value = g), (resources.ut_floorMap.value = h));
    let _ = resources.sm_car.meshData;
    (Object.values(_.meshes).forEach((m) => {
      m.layers.enable(resources.LAYER_PLANE_REFLECT);
    }),
      Object.values(_.materials).forEach((m) => {
        ((m.aoMap = resources.ut_car_body_ao.value),
          m instanceof MeshStandardMaterial &&
            (m.onBeforeCompile = (D) => {
              AA(D);
            }));
      }),
      (_.materials.Car_body.map = resources.ut_white.value),
      (_.materials.Car_body.needsUpdate = !0),
      (_.materials.M_logo.map.anisotropy = 8));
    const A = _.materials.Car_window;
    ((A.map = resources.ut_white.value),
      (A.roughnessMap = resources.ut_dark.value),
      (A.metalnessMap = resources.ut_white.value),
      resources.u_m_car_window_orignData.color.copy(A.color),
      (resources.u_m_car_window_orignData.opacity = A.opacity),
      (resources.u_m_car_window_orignData.roughness = A.roughness),
      (A.needsUpdate = !0),
      (_ = resources.sm_car_lightbar.meshData),
      (resources.sm_car_lightbar.visible = !1),
      Object.values(_.meshes).forEach((m) => {
        m.layers.enable(resources.LAYER_PLANE_REFLECT);
      }),
      Object.values(_.materials).forEach((m) => {
        ((m.toneMapped = !1),
          m instanceof MeshStandardMaterial &&
            (m.onBeforeCompile = (D) => {
              (AA(D), m.name == "lightbar_Baked" && UO(D));
            }));
      }),
      (_ = resources.sm_startroom.meshData),
      Object.values(_.materials).forEach((m) => {
        ((m.aoMap = resources.ut_startroom_ao.value),
          (m.lightMap = resources.ut_startroom_light.value),
          (m.normalMap = resources.ut_floor_normal.value),
          (m.roughnessMap = resources.ut_floor_roughness.value),
          (m.envMapIntensity = 0));
      }),
      (_ = resources.sm_speedup.meshData),
      _.meshes.forEach((m) => {
        ((m.material = kO),
          m.layers.enable(resources.LAYER_CAPTURE),
          m.layers.enable(resources.LAYER_PLANE_REFLECT));
      }),
      (_ = resources.sm_size.meshData),
      Object.values(_.materials).forEach((m) => {
        ((m.transparent = !0), (m.needsUpdate = !0), (m.map.anisotropy = 4));
      }),
      (_ = resources.sm_curvature.meshData),
      _.meshes.forEach((m) => {
        m.name == "曲率" &&
          ((m.material = NO),
          (_.materials.m_curvature = m.material),
          m.layers.enable(resources.LAYER_CAPTURE));
      }),
      Object.values(_.materials).forEach((m) => {
        ((m.transparent = !0), (m.needsUpdate = !0));
      }),
      (_ = resources.sm_windspeed.meshData),
      _.meshes.forEach((m) => {
        ((m.material = zO),
          (_.materials.m_windLine = m.material),
          m.layers.enable(resources.LAYER_CAPTURE));
      }),
      (_ = resources.sm_linecar.meshData),
      _.meshes.forEach((m) => {
        ((m.material = GO), (_.materials.m_linecar = m.material));
      }),
      (_ = resources.sm_carradar.meshData),
      _.meshes.forEach((m) => {
        ((m.material = HO),
          (_.materials.m_carradar = m.material),
          m.layers.enable(resources.LAYER_CAPTURE));
      }),
      (_ = resources.sm_simpleCar.meshData),
      _.meshes.forEach((m) => {
        ((m.material = Ag), (_.materials.m_simpleCar = m.material), (m.renderOrder = 10));
      }));
  }
  _createScene() {
    const r = this.viewer;
    (resourceConfig.DEBUG,
      (this._posterGenerator = r.addNode(PhotoComposer)),
      (this._posterGenerator.enabled = !1),
      (r.scene.background = new Color(0, 0, 0)));
    const s = r.addNode(PlanarReflection);
    ((resources.u_reflect.u_reflectMatrix.value = s.reflectMatrix),
      (resources.u_reflect.u_reflectTexture.value = s.reflectTexture),
      resources.sm_startroom.traverse((Be) => {
        (Be.name === "ReflecFloor" || Be.name === "Floor") && FO(Be);
      }));
    const h = r.addNode(
        new EnvironmentController(resources.ut_env_night.value, resources.ut_env_light.value),
      ),
      l = r.addNode(resources.sm_startroom),
      g = r.addNode(new TaillightController(l)),
      _ = new dO();
    (this.viewer.addComponent(resources.sm_car, _),
      _.probeBoxMin.set(-3, -0.1, -1.5),
      _.probeBoxMax.set(3.6, 3, 1.5));
    const A = this.viewer.addNode(resources.sm_car),
      m = r.addNode(new HeadlightController(A)),
      D = r.addNode(
        new SpringCamera({
          springLength: 11,
          rotation: new Euler(0, Math.PI * 0.5, 0),
          fov: 33.4,
          lookAt: new Vector3(0, 0.8, 0),
        }),
      ),
      U = r.addNode(
        new OrbitController({
          springCamera: D,
        }),
      );
    r.addNode(PointerEffects);
    const R = r.addNode(new WheelMotion(A, U));
    r.addNode(resources.sm_speedup);
    const ne = r.addNode(MovingSensor),
      ce = r.addNode(LightbarController),
      xe = r.addNode(DimensionsEffect),
      Se = r.addNode(CurvatureEffect),
      $ = r.addNode(WindEffect),
      q = r.addNode(LineCarEffect),
      N = r.addNode(SensorPoints),
      ie = r.addNode(RadarEffect),
      _e = r.addNode(TrafficEffect),
      Pe = r.addPlugin(
        new K3({
          luminanceThreshold: 0,
          luminanceSmoothing: 1.6,
          mipmapBlur: !0,
        }),
      );
    (r.addPlugin(fO),
      (this._envController = h),
      (this._springCtr = U),
      (this._carLightController = m),
      (this._topLightController = g),
      (this._carSpeedUpdate = R),
      (this._bloom = Pe),
      (this._projectionProbe = _),
      (this._accessories = {
        s1_c: ne,
        s1_cpcl: ce,
        s2_b: xe,
        s2_c: Se,
        s3_b: $,
        s3_c: q,
        s4_b: N,
        s4_c: ie,
        s4_cSC: _e,
      }),
      this.eventRegister());
  }
  _compileScene() {
    (BO(), this.viewer.compile(), events.emit(events.PRELOADED));
    let r = resources.getCustomParams();
    r && events.emit(events.CHANGECOLOR, r);
  }
  eventRegister() {
    const r = this._envController,
      s = this._springCtr,
      h = this._carLightController,
      l = this._topLightController,
      g = this._carSpeedUpdate,
      _ = this._bloom,
      A = this._projectionProbe,
      m = this._accessories,
      D = (_e = 1, Pe = 1, Be = 1, Re = 1, ct = 1.8) => {
        (Tweening.TweenManager.KillTweensOf(A),
          Tweening.TweenManager.Timeline(A)
            .to(
              {
                probeCenter: new Vector3(0, 0, 0),
                probeBoxMax: new Vector3(3.6, 3, 1.5),
              },
              1,
              {
                easing: Tweening.Easing.Cubic.InOut,
                onUpdate: () => {
                  A.probeCenter = A.probeCenter;
                },
              },
            )
            .start(),
          Tweening.TweenManager.KillTweensOf(resources.u_floorLightMapIntensity),
          Tweening.TweenManager.Timeline(resources.u_floorLightMapIntensity)
            .to(
              {
                value: _e,
              },
              1,
            )
            .start(),
          Tweening.TweenManager.KillTweensOf(resources.u_car_envMapIntensity),
          Tweening.TweenManager.Timeline(resources.u_car_envMapIntensity)
            .to(
              {
                value: Pe,
              },
              1.5,
              {
                easing: Tweening.Easing.Cubic.InOut,
              },
            )
            .start(),
          Tweening.TweenManager.KillTweensOf(this._environment),
          Tweening.TweenManager.Tween(this._environment)
            .to(
              {
                exposure: Be,
              },
              1,
            )
            .start(),
          Tweening.TweenManager.KillTweensOf(l),
          Tweening.TweenManager.Timeline(l)
            .to(
              {
                opacity: Re,
              },
              0.5,
              {},
            )
            .start(),
          Tweening.TweenManager.KillTweensOf(_),
          Tweening.TweenManager.Timeline(_)
            .to(
              {
                luminanceSmoothing: ct,
              },
              2,
              {},
            )
            .start());
      },
      U = new Color("#000000"),
      R = new Color("#C9D573"),
      ne = new Color("#ffffff"),
      ce = new Color(),
      xe = new Color();
    events.on(events.UPDATESHOWINGSTATE, (_e) => {
      for (let Pe in m) m[Pe].hide();
      switch (
        (this._posterGenerator.hide(),
        (g.targetVelocity = 0),
        s.setNewRange(),
        xe.copy(resources.u_floorLightMapColor.value),
        _e)
      ) {
        case ShowState.BeginAnim:
          (Tweening.TweenManager.KillTweensOf(r),
            Tweening.TweenManager.Timeline(r)
              .delay(1.5)
              .call(() => {
                (r.setState(U_.night, 2.5, Tweening.Easing.Cubic.In),
                  s
                    .gotoPOI(new Vector3(0, 0.8, 0), 7, new Euler(0, Math.PI * 0.5, 0), 4)
                    .then(() => {
                      const Pe = resources.getCustomParams();
                      (Pe == "custom"
                        ? (events.emit(events.UPDATESHOWINGSTATE, ShowState.State5),
                          events.emit(
                            events.UPDATECOLORTABLESTATE,
                            ColorPanelState.customColorTable,
                          ))
                        : Pe
                          ? (events.emit(events.UPDATESHOWINGSTATE, ShowState.State5),
                            events.emit(
                              events.UPDATECOLORTABLESTATE,
                              ColorPanelState.presetColorTable,
                            ))
                          : events.emit(events.UPDATESHOWINGSTATE, ShowState.State1),
                        (s.enableControlCamera = !0));
                    }));
              })
              .delay(2.5)
              .call(() => {
                r.setState(U_.light, 4, Tweening.Easing.Cubic.Out);
              })
              .start(),
            Tweening.TweenManager.KillTweensOf(l),
            Tweening.TweenManager.Timeline(l)
              .delay(1.5)
              .to({}, 2.5, {
                onUpdate: (Pe, Be) => {
                  (ce.copy(U).lerp(R, Be),
                    (l.lightEmissiveColor = ce),
                    (l.lightEmissiveIntensity = Be * 0.4));
                },
              })
              .to({}, 2, {
                onUpdate: (Pe, Be) => {
                  (ce.copy(R).lerpHSL(ne, Be),
                    (l.lightEmissiveColor = ce),
                    (l.lightEmissiveIntensity = Be * 2.3 + 0.4));
                },
              })
              .start(),
            Tweening.TweenManager.KillTweensOf(h),
            Tweening.TweenManager.Timeline(h)
              .delay(1)
              .to(
                {
                  lightValue: 1,
                },
                1,
                {
                  easing: Tweening.Easing.Cubic.In,
                },
              )
              .start(),
            Tweening.TweenManager.KillTweensOf(resources.u_floorLightMapIntensity),
            Tweening.TweenManager.Timeline(resources.u_floorLightMapIntensity)
              .delay(1.5)
              .to(
                {
                  value: 0.1,
                },
                2.5,
                {
                  easing: Tweening.Easing.Cubic.In,
                  onUpdate: (Pe, Be) => {
                    (ce.copy(xe).lerpHSL(R, Be), resources.u_floorLightMapColor.value.copy(ce));
                  },
                },
              )
              .to(
                {
                  value: 1,
                },
                2,
                {
                  easing: Tweening.Easing.Linear.None,
                  onUpdate: (Pe, Be) => {
                    (ce.copy(R).lerpHSL(ne, Be), resources.u_floorLightMapColor.value.copy(ce));
                  },
                },
              )
              .start(),
            Tweening.TweenManager.KillTweensOf(resources.u_floorReflectIntensity),
            Tweening.TweenManager.Timeline(resources.u_floorReflectIntensity)
              .delay(1.8)
              .to(
                {
                  value: 0.1,
                },
                1.5,
                {
                  easing: Tweening.Easing.Cubic.In,
                },
              )
              .to(
                {
                  value: 1,
                },
                1.5,
                {
                  easing: Tweening.Easing.Linear.None,
                },
              )
              .start());
          break;
        case ShowState.State1:
          (s.setNewTarget(new Vector3(0, 0.8, 0), 7, new Euler(0, Math.PI * 0.5, 0)),
            D(),
            (s.targetFov = 33.4));
          break;
        case ShowState.State2:
          (s.setNewTarget(new Vector3(0, 0.8, 0), 7, new Euler(0, -0.89, 0.1)),
            m.s2_b.show(),
            (s.targetFov = 33.4),
            D());
          break;
        case ShowState.State3:
          (s.setNewTarget(new Vector3(0.3, 0.8, 0), 7, new Euler(0, 0.65, 0.1)),
            m.s3_b.show(),
            D(0, 0, 10, 0, 0.5),
            (s.targetFov = 33.4),
            Tweening.TweenManager.KillTweensOf(A),
            Tweening.TweenManager.Timeline(A)
              .to(
                {
                  probeCenter: new Vector3(0, 0.5, 0),
                  probeBoxMax: new Vector3(3.6, 1.6, 1.5),
                },
                1,
                {
                  easing: Tweening.Easing.Cubic.InOut,
                  onUpdate: () => {
                    A.probeCenter = A.probeCenter;
                  },
                },
              )
              .start());
          break;
        case ShowState.State4:
          (s.setNewTarget(new Vector3(0.3, 0.8, 0), 14, new Euler(0, Math.PI, 1.2)),
            s.setNewRange([0.2, 1.3]),
            D(0.2, 1, 3, 0, 1.5),
            (s.targetFov = 33.4),
            m.s4_b.show());
          break;
        case ShowState.State5:
          (s.setNewTarget(new Vector3(0.2, 0.8, 0), 7, new Euler(0, -0.7, 0.03)),
            D(1, 1, 1, 0, 1.8),
            (s.targetFov = 33.4),
            this._posterGenerator.show());
          break;
      }
    });
    let Se = !1,
      $ = ShowState.BeginAnim;
    events.on(events.CLICKEFFECT, (_e) => {
      if (Se !== _e || $ !== events.currentShowingState)
        ((Se = _e),
          ($ = events.currentShowingState),
          events.emit(events.PRESSED_STATE_CHANGED, Se, $));
      else return;
      for (let Pe in m) m[Pe].hide();
      switch (events.currentShowingState) {
        case ShowState.State1:
          Se
            ? ((g.targetVelocity = 8),
              (g.lerpStrength = 0.5),
              (s.targetFov = 60),
              (s.springlengthOffset = -3),
              (s.lerpStrength = 0.5),
              m.s1_c.show(),
              m.s1_cpcl.show(0.5, 0.2),
              D(0, 0.1, 1, 0, 0),
              Tweening.TweenManager.KillTweensOf(resources.u_carMetalness),
              Tweening.TweenManager.Timeline(resources.u_carMetalness)
                .to(
                  {
                    value: Math.max(0, resources.u_carMetalness.value - 0.3),
                  },
                  0.8,
                  {
                    easing: Tweening.Easing.Cubic.In,
                  },
                )
                .start())
            : ((g.targetVelocity = 0),
              (g.lerpStrength = 1.5),
              (s.targetFov = 33.4),
              (s.lerpStrength = 1.5),
              (s.springlengthOffset = 0),
              D(),
              Tweening.TweenManager.KillTweensOf(resources.u_carMetalness),
              Tweening.TweenManager.Timeline(resources.u_carMetalness)
                .to(
                  {
                    value: resources.colors.get(events.currentColorIndex).metal ?? 0,
                  },
                  1,
                )
                .start());
          break;
        case ShowState.State2:
          Se
            ? (m.s2_c.show(), (s.targetFov = 45), (s.lerpStrength = 0.5))
            : (m.s2_b.show(), (s.targetFov = 33.4), (s.lerpStrength = 0.5));
          break;
        case ShowState.State3:
          Se
            ? (m.s3_c.show(1, 0.2),
              (s.targetFov = 60),
              (s.springlengthOffset = -3),
              (s.lerpStrength = 1.5))
            : (m.s3_b.show(),
              (s.targetFov = 33.4),
              (s.springlengthOffset = 0),
              (s.lerpStrength = 1.5));
          break;
        case ShowState.State4:
          Se
            ? ((g.targetVelocity = 16),
              (g.lerpStrength = 0.5),
              m.s4_c.show(),
              m.s4_cSC.show(),
              m.s1_c.show(),
              m.s1_cpcl.show(0.5, 0.2),
              (s.targetFov = 25),
              (s.lerpStrength = 1.5),
              (s.springlengthOffset = 20),
              (s.moveSpeed = [0.1, 0.1]),
              D(0.2, 0.3, 3, 0, 1.5))
            : ((g.targetVelocity = 0),
              (g.lerpStrength = 1.5),
              (s.targetFov = 33.4),
              (s.lerpStrength = 1.5),
              (s.springlengthOffset = 0),
              (s.moveSpeed = [1, 1]),
              m.s4_b.show(),
              D(0.2, 1, 3, 0, 1.5));
          break;
      }
    });
    const q = new Color(0, 0, 0);
    let N = !1,
      ie = "0";
    events.on(events.CHANGECOLOR, (_e) => {
      _e == "11"
        ? (resources.sm_car_lightbar.visible = !0)
        : (resources.sm_car_lightbar.visible = !1);
      const {
          col: Pe,
          tcar: Be,
          tw: Re,
          twr: ct,
          metal: et,
          rough: Ze,
          tf: Nt,
        } = resources.colors.get(_e),
        Bt = resources.sm_car.meshData.materials.Car_body;
      ((Bt.map = Be ? Be.value : resources.ut_white.value),
        (Be || N) && resources.u_carColor.value.copy(q),
        (N = !!Be),
        ie != "custom" || _e != "custom"
          ? (Tweening.TweenManager.KillTweensOf(resources.u_carColor),
            Tweening.TweenManager.Timeline(resources.u_carColor)
              .to(
                {
                  value: Pe,
                },
                0.2,
              )
              .start(),
            Tweening.TweenManager.KillTweensOf(resources.u_carRoughness),
            Tweening.TweenManager.Timeline(resources.u_carRoughness)
              .to(
                {
                  value: Ze ?? 0,
                },
                0.2,
              )
              .start(),
            Tweening.TweenManager.KillTweensOf(resources.u_carMetalness),
            Tweening.TweenManager.Timeline(resources.u_carMetalness)
              .to(
                {
                  value: et ?? 0,
                },
                0.2,
              )
              .start())
          : (resources.u_carColor.value.copy(Pe),
            (resources.u_carRoughness.value = Ze),
            (resources.u_carMetalness.value = et)),
        (ie = _e),
        Re && ct
          ? ((resources.sm_car.meshData.materials.Car_window.color = new Color(
              "#fff",
            ).convertSRGBToLinear()),
            (resources.sm_car.meshData.materials.Car_window.opacity = 1),
            (resources.sm_car.meshData.materials.Car_window.roughness = 1),
            (resources.sm_car.meshData.materials.Car_window.map = Re.value),
            (resources.sm_car.meshData.materials.Car_window.roughnessMap = ct.value),
            (resources.sm_car.meshData.materials.Car_window.metalnessMap = ct.value))
          : ((resources.sm_car.meshData.materials.Car_window.color =
              resources.u_m_car_window_orignData.color),
            (resources.sm_car.meshData.materials.Car_window.opacity =
              resources.u_m_car_window_orignData.opacity),
            (resources.sm_car.meshData.materials.Car_window.roughness =
              resources.u_m_car_window_orignData.roughness),
            (resources.sm_car.meshData.materials.Car_window.map = resources.ut_white.value),
            (resources.sm_car.meshData.materials.Car_window.roughnessMap = resources.ut_dark.value),
            (resources.sm_car.meshData.materials.Car_window.metalnessMap =
              resources.ut_white.value)),
        (resources.ut_floorMap.value = Nt ? Nt.value : resources.ut_white.value));
    });
  }
  update(r) {
    if (
      ((resources.u_speedTime.value += r * resources.u_speedUpBackgroundValue.value * 0.2),
      (resources.u_time.value += r),
      resources.sm_car)
    ) {
      const s = resources.sm_car.meshData.materials.Car_body;
      ((s.metalness = resources.u_carMetalness.value),
        (s.roughness = resources.u_carRoughness.value),
        s.color.copy(resources.u_carColor.value));
    }
  }
}
export { LightbarController, bB, wB, AB, SectionInspector, Experience };
