import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    B: () => m,
  });
  var s = r(861),
    h = r(41),
    l = r(25),
    g = function (D, U, R, ne) {
      var ce = arguments.length,
        xe = ce < 3 ? U : ne === null ? (ne = Object.getOwnPropertyDescriptor(U, R)) : ne,
        Se;
      if (typeof Reflect == "object" && typeof Reflect.decorate == "function")
        xe = Reflect.decorate(D, U, R, ne);
      else
        for (var $ = D.length - 1; $ >= 0; $--)
          (Se = D[$]) && (xe = (ce < 3 ? Se(xe) : ce > 3 ? Se(U, R, xe) : Se(U, R)) || xe);
      return (ce > 3 && xe && Object.defineProperty(U, R, xe), xe);
    };
  const _ = `
varying vec2 vUv;

void main() {
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`,
    A = `
uniform sampler2D texFont;
varying vec2 vUv;

uniform vec4  diffuse;
uniform vec4  stroke;
uniform vec4  shadow;
uniform vec2  shadowOffset;
uniform float weight;

float median(in float r, in float g, in float b) {
    return max(min(r, g), min(max(r, g), b));
}

float signedDistance(in vec2 uv) {
    vec4 texel = texture2D(texFont, uv);
    return median(texel.r, texel.g, texel.b) - 0.5;
}

void main() {
    vec4 color = vec4(diffuse);
    float d = signedDistance(vUv) + weight;
    float w = fwidth(d);

    if (stroke.a > 0.0) {
        vec4 strokeColor = vec4(stroke.rgb, smoothstep(-w, w, d));
        color.a *= smoothstep(-w, w, d - stroke.a);
        color = mix(strokeColor, color, color.a);
    }
    else {
        color.a *= smoothstep(-w, w, d);
    }

    if (shadow.a > 0.0) {
        float dd = signedDistance(vUv + shadowOffset);
        vec4 shadowColor = vec4(shadow.rgb, smoothstep(-w - shadow.a, w + shadow.a, dd));
        color = mix(shadowColor, color, color.a);
    }

    gl_FragColor = color;
}
`;
  class m extends l.jyz {
    constructor() {
      super(...arguments);
      B(this, "vertexShader", _);
      B(this, "fragmentShader", A);
      B(this, "blending", l.bdR);
      B(this, "transparent", !0);
      B(this, "depthWrite", !1);
      B(this, "uniforms", {
        texFont: {
          value: null,
        },
        diffuse: {
          value: (0, s.bd)(1),
        },
        stroke: {
          value: (0, s.bd)(0),
        },
        shadow: {
          value: (0, s.bd)(0),
        },
        shadowOffset: {
          value: (0, s.i5)(-0.001, 0.001),
        },
        weight: {
          value: 0.2,
        },
      });
      B(this, "_strokeColor", (0, s.$c)());
      B(this, "_shadowColor", (0, s.$c)());
    }
    get color() {
      return this.uniforms.diffuse.value;
    }
    set color(R) {
      this.uniforms.diffuse.value = R;
    }
    get weight() {
      return this.uniforms.weight.value;
    }
    set weight(R) {
      this.uniforms.weight.value = R;
    }
    get strokeColor() {
      return (0, s.OE)(this.uniforms.stroke.value, this._strokeColor);
    }
    set strokeColor(R) {
      (0, s.eC)(R, this.uniforms.stroke.value);
    }
    get strokeWidth() {
      return this.uniforms.stroke.value.w;
    }
    set strokeWidth(R) {
      this.uniforms.stroke.value.w = R;
    }
    get shadowBlur() {
      return this.uniforms.shadow.value.w;
    }
    set shadowBlur(R) {
      this.uniforms.shadow.value.w = R;
    }
    get shadowColor() {
      return (0, s.OE)(this.uniforms.shadow.value, this._shadowColor);
    }
    set shadowColor(R) {
      (0, s.eC)(R, this.uniforms.shadow.value);
    }
    get shadowOffset() {
      return this.uniforms.shadowOffset.value;
    }
    set shadowOffset(R) {
      this.uniforms.shadowOffset.value = R;
    }
    get texFont() {
      return this.uniforms.texFont.value;
    }
  }
  (g(
    [
      (0, h.Cb)({
        type: "Color",
      }),
    ],
    m.prototype,
    "color",
    null,
  ),
    g(
      [
        (0, h.Cb)({
          min: 0,
          max: 1,
          step: 0.01,
        }),
      ],
      m.prototype,
      "weight",
      null,
    ),
    g(
      [
        (0, h.Cb)({
          dir: "stroke",
        }),
      ],
      m.prototype,
      "strokeColor",
      null,
    ),
    g(
      [
        (0, h.Cb)({
          min: 0,
          max: 1,
          step: 0.01,
          dir: "stroke",
        }),
      ],
      m.prototype,
      "strokeWidth",
      null,
    ),
    g(
      [
        (0, h.Cb)({
          min: 0,
          max: 1,
          step: 0.01,
          dir: "shadow",
        }),
      ],
      m.prototype,
      "shadowBlur",
      null,
    ),
    g(
      [
        (0, h.Cb)({
          dir: "shadow",
        }),
      ],
      m.prototype,
      "shadowColor",
      null,
    ),
    g(
      [
        (0, h.Cb)({
          dir: "shadow",
        }),
      ],
      m.prototype,
      "shadowOffset",
      null,
    ),
    g([(0, h.Cb)()], m.prototype, "texFont", null));
};
