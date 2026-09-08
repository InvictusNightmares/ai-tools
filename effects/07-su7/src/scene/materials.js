import shader1 from "../shaders/materials-01.glsl?raw";
import shader2 from "../shaders/materials-02.glsl?raw";
import shader3 from "../shaders/materials-03.glsl?raw";
import shader4 from "../shaders/materials-04.glsl?raw";
import shader5 from "../shaders/materials-05.glsl?raw";
import shader6 from "../shaders/materials-06.glsl?raw";
import shader7 from "../shaders/materials-07.glsl?raw";
import shader8 from "../shaders/materials-08.glsl?raw";
import shader9 from "../shaders/materials-09.glsl?raw";
import shader10 from "../shaders/materials-10.glsl?raw";
import shader11 from "../shaders/materials-11.glsl?raw";
import shader12 from "../shaders/materials-12.glsl?raw";
import shader13 from "../shaders/materials-13.glsl?raw";
import shader14 from "../shaders/materials-14.glsl?raw";
import shader15 from "../shaders/materials-15.glsl?raw";
import shader16 from "../shaders/materials-16.glsl?raw";
import shader17 from "../shaders/materials-17.glsl?raw";
import { resources } from "./../config/resources.js";
import {
  Color,
  UniformsLib,
  ShaderMaterial,
  DoubleSide,
  Vector4,
  AdditiveBlending,
  MeshMatcapMaterial,
} from "./../engine/index.js";
const wg = shader1,
  DO = shader2,
  If = shader3,
  LO = shader4,
  IO = shader5,
  OO = shader6;
function BO() {
  Ag.matcap = resources.ut_scar_matcap.value;
}
function FO(t) {
  if (!t) {
    console.warn("ReflectMaterial: no mesh parameter");
    return;
  }
  const n = {
      color: {
        value: new Color(),
      },
      map: resources.ut_floorMap,
      opacity: {
        value: 1,
      },
      roughness: {
        value: 1,
      },
      roughnessMap: {
        value: null,
      },
      metalness: {
        value: 1,
      },
      metalnessMap: {
        value: null,
      },
      aoMap: {
        value: null,
      },
      lightMap: {
        value: null,
      },
      lightMapColor: resources.u_floorLightMapColor,
      lightMapIntensity: {
        value: 1,
      },
      emissive: {
        value: new Color(),
      },
      emissiveMap: {
        value: null,
      },
      normalMap: {
        value: null,
      },
      distortionScale: {
        value: 0,
      },
      u_lightIntensity: resources.u_floorLightMapIntensity,
      u_reflectIntensity: resources.u_floorReflectIntensity,
      u_floor_typeSwitch: resources.u_floor_typeSwitch,
      ut_street: resources.ut_street,
      u_floorUVOffset: resources.u_floorUVOffset,
      ...UniformsLib.fog,
      ...UniformsLib.lights,
      ...resources.u_reflect,
    },
    r = {},
    s = t.material;
  if (s) {
    ((n.color = {
      value: s.color,
    }),
      (r.USE_MAP = ""),
      (n.opacity = {
        value: s.opacity,
      }),
      s.roughnessMap &&
        ((n.roughnessMap = {
          value: s.roughnessMap,
        }),
        (r.USE_ROUGHNESS_MAP = "")),
      (n.metalness = {
        value: s.metalness,
      }),
      s.metalnessMap &&
        ((n.metalnessMap = {
          value: s.metalnessMap,
        }),
        (r.USE_METALNESS_MAP = "")),
      (n.emissive = {
        value: s.emissive,
      }),
      s.emissiveMap &&
        ((n.emissiveMap = {
          value: s.emissiveMap,
        }),
        (r.USE_EMISSIVE_MAP = "")),
      s.aoMap &&
        ((n.aoMap = {
          value: s.aoMap,
        }),
        (r.USE_AO_MAP = "")),
      (n.lightMapIntensity = {
        value: s.lightMapIntensity,
      }),
      s.lightMap &&
        ((n.lightMap = {
          value: s.lightMap,
        }),
        (r.USE_LIGHT_MAP = "")),
      s.normalMap &&
        ((s.normalMap.anisotropy = 4),
        (n.normalMap = {
          value: s.normalMap,
        }),
        (r.USE_NORMAL_MAP = "")));
    const h = new ShaderMaterial({
      defines: r,
      uniforms: n,
      vertexShader: IO,
      fragmentShader: LO,
    });
    ((h.name = "M_Reflect"), (t.material = h));
  } else console.log("ReflectMaterial: not a MeshStandardMaterial");
}
const kO = new ShaderMaterial({
  uniforms: {
    time: resources.u_speedTime,
    vSpeed: resources.u_speedUpBackgroundValue,
    vPoliceColorChange: resources.u_policeColorChange,
  },
  vertexShader: If,
  fragmentShader: `
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    varying vec3 vPositionW;
    varying vec3 vNormalW;

    uniform float vPoliceColorChange;
    uniform float vSpeed;
    uniform float time;

    ${wg}
    ${DO}
    void main() {
        vec2 uv_0 = vUv+vec2(-time*0.5,0.);
        float noiseMask = (noise2d(uv_0*vec2(3.,100.))+1.)/2.;
        noiseMask = pow(clamp(noiseMask-0.1,0.,1.),11.);
        noiseMask = smoothstep(0.0,0.04,noiseMask)*2.;

        vec3 colorNoiseMask = colorNoise(uv_0*vec2(10.,100.))*vec3(1.5,1.,400.);
        noiseMask*=smoothstep(0.02,0.5,vUv.x)*smoothstep(0.02,0.5,1.-vUv.x);
        noiseMask*=smoothstep(0.01,0.1,vUv.y)*smoothstep(0.01,0.1,1.-vUv.y);

        noiseMask*=smoothstep(1.,10.,vSpeed);

        colorNoiseMask = clamp(colorNoiseMask,vec3(0.),vec3(1.));

        vec3 policeColor = mix(vec3(3.,.3,.3),vec3(0.3,0.3,3.),vec3(smoothstep(0.10,0.30,colorNoiseMask.g)));
        colorNoiseMask = mix(colorNoiseMask,policeColor,vec3(vPoliceColorChange));

        gl_FragColor = vec4(vec3(colorNoiseMask),noiseMask);
        // #include <tonemapping_fragment>
        // #include <encodings_fragment>
    }
    `,
  depthWrite: !1,
  transparent: !0,
});
function AA(t) {
  let n = t.fragmentShader,
    r = t.vertexShader;
  ((r = r.replace("#include <common>", shader7)),
    (r = r.replace("#include <fog_vertex>", shader8)),
    (n = n.replace(
      "#include <common>",
      `
            #include <common>
            varying vec3 reflectVec;
            varying vec3 vPosW;
            uniform samplerCube cubeCaptureReflectMap;
            uniform samplerCube blurCaptureReflectMap;
            uniform float vEnvMapIntensity;
            uniform float vDiscardOpacity;
            ${wg}
            #if (!defined(USE_UV))
                #define USE_UV
            #endif
            
            `,
    )),
    (n = n.replace("#include <envmap_physical_pars_fragment>", shader9)),
    (n = n.replace(
      "#include <clipping_planes_fragment>",
      `

            float discardMask = (noise2d(vUv*15.)+1.)/2.;
            float mm = 1.-(vPosW.x+2.7)/5.4;
            if(mm < (1. - vDiscardOpacity)) discard;
            #include <clipping_planes_fragment>
            `,
    )),
    (n = n.replace("#include <dithering_fragment>", shader10)),
    (t.uniforms.cubeCaptureReflectMap = resources.ut_cubeCapture),
    (t.uniforms.blurCaptureReflectMap = resources.ut_blurCapture),
    (t.uniforms.vEnvMapIntensity = resources.u_car_envMapIntensity),
    (t.uniforms.vDiscardOpacity = resources.u_car_discard),
    (t.vertexShader = r),
    (t.fragmentShader = n));
}
function UO(t) {
  let n = t.fragmentShader,
    r = t.vertexShader;
  ((r = r.replace("#include <common>", shader11)),
    (r = r.replace(
      "#include <fog_vertex>",
      `
            #include <fog_vertex>
            vUv2 = uv2;
            `,
    )),
    (n = n.replace("#include <common>", shader12)),
    (n = n.replace("#include <emissivemap_fragment>", shader13)),
    (t.uniforms.timer = resources.u_time),
    (t.vertexShader = r),
    (t.fragmentShader = n));
}
const NO = new ShaderMaterial({
    name: "m_curvature",
    uniforms: {
      opacity: {
        value: 1,
      },
      vColor: {
        value: new Color("#fdffc7"),
      },
      tSaLine: resources.ut_saLine,
      time: resources.u_time,
    },
    vertexShader: If,
    fragmentShader: shader14,
    depthWrite: !1,
    side: DoubleSide,
    transparent: !0,
  }),
  zO = new ShaderMaterial({
    name: "m_windLine",
    uniforms: {
      vNoiseParams_alpha: {
        value: new Vector4(6, 2, 2, 0.5),
      },
      vNoiseParams_wave: {
        value: new Vector4(2, 1, 1, 0.5),
      },
      vIntensity: {
        value: 3,
      },
      vColor: {
        value: new Color("#cdeffe"),
      },
      tSaLine: resources.ut_saLine,
      time: resources.u_time,
      opacity: {
        value: 1,
      },
    },
    vertexShader: If,
    fragmentShader: `
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    varying vec3 vPositionW;
    varying vec3 vNormalW;

    uniform vec4 vNoiseParams_alpha;
    uniform vec4 vNoiseParams_wave;
    uniform float vIntensity;
    uniform vec3 vColor;
    uniform float time;
    uniform float opacity;
    uniform sampler2D tSaLine;
    ${wg}

    void main() {
        float noiseMask_alpha = noise2d((vUv+vec2(0.,time*vNoiseParams_alpha.w))*vNoiseParams_alpha.xy)*vNoiseParams_alpha.z;
        float noiseMask_wave = noise2d((vUv+vec2(0.,time*vNoiseParams_wave.w))*vNoiseParams_wave.xy)*vNoiseParams_wave.z;
        vec2 l_uv = vUv*10.;
        float mask = texture(tSaLine,l_uv+vec2(noiseMask_wave,0.)).r;
        // float mask = texture(tSaLine,l_uv).r;
        mask*=(smoothstep(0.,0.5,vUv.y))*(1.-smoothstep(0.5,1.,vUv.y));

        gl_FragColor = vec4(vec3(vColor),clamp(mask*(noiseMask_alpha+0.5)*vIntensity*opacity,0.,1.));
    }
    `,
    transparent: !0,
    depthWrite: !1,
    side: DoubleSide,
  }),
  GO = new ShaderMaterial({
    name: "m_linecar",
    uniforms: {
      time: resources.u_time,
      opacity: {
        value: 1,
      },
      vNoiseParams_wave: {
        value: new Vector4(1, 20, 10, 1.2),
      },
    },
    vertexShader: If,
    fragmentShader: `
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    varying vec3 vPositionW;
    varying vec3 vNormalW;
    varying vec3 vColor;

    uniform float time;
    uniform float opacity;
    uniform vec4 vNoiseParams_wave;
    ${wg}

    void main() {
        float noiseMask_alpha = noise2d((vUv+vec2(time*vNoiseParams_wave.w,0.))*vNoiseParams_wave.xy)*vNoiseParams_wave.z;
        float mask = noiseMask_alpha*(smoothstep(0.05,0.4,vUv.x))*(1.-smoothstep(0.6,0.95,vUv.x));
        mask = mask*(smoothstep(0.05,0.4,vUv.y))*(1.-smoothstep(0.6,0.95,vUv.y));
        gl_FragColor = vec4(clamp(vec3(vColor*2.),0.,1.),clamp(mask*opacity,0.,1.));
    }

    `,
    transparent: !0,
    depthWrite: !1,
    blending: AdditiveBlending,
    side: DoubleSide,
  }),
  HO = new ShaderMaterial({
    name: "m_carradar",
    uniforms: {
      time: resources.u_time,
      opacity: {
        value: 1,
      },
      uColor: {
        value: new Color("#88eeff"),
      },
      uCenter1: resources.u_simpleCarCenter1,
      uCenter2: resources.u_simpleCarCenter2,
    },
    vertexShader: If,
    fragmentShader: shader15,
    transparent: !0,
    depthWrite: !1,
    blending: AdditiveBlending,
    side: DoubleSide,
  }),
  Ag = new MeshMatcapMaterial({
    transparent: !0,
    blending: AdditiveBlending,
  });
Ag.onBeforeCompile = (t) => {
  let n = t.fragmentShader,
    r = t.vertexShader;
  ((r = r.replace(
    "#include <common>",
    `
        #include <common>
        varying vec3 vWorldPosition;
        `,
  )),
    (r = r.replace(
      "#include <fog_vertex>",
      `
        #include <fog_vertex>
        vWorldPosition = vec3( modelMatrix*vec4( position, 1.0 ));
        `,
    )),
    (n = n.replace(
      "#include <common>",
      `
        #include <common>
        varying vec3 vWorldPosition;
        `,
    )),
    (n = n.replace("vec4 diffuseColor = vec4( diffuse, opacity );", shader16)),
    (t.vertexShader = r),
    (t.fragmentShader = n));
};
const SA = new ShaderMaterial({
  name: "m_radarPoints",
  uniforms: {
    time: resources.u_time,
    opacity: {
      value: 0,
    },
    vColor: {
      value: new Color("#fff"),
    },
  },
  vertexShader: OO,
  fragmentShader: shader17,
  blending: AdditiveBlending,
  depthWrite: !1,
  transparent: !0,
});
export { wg, DO, If, LO, IO, OO, BO, FO, kO, AA, UO, NO, zO, GO, HO, Ag, SA };
