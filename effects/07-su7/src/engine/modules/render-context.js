import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    c: () => A,
  });
  var s = r(25),
    h = r(774);
  const l = `
varying vec2      vUv;
uniform sampler2D tMain;
uniform float     uLod;

void main() {
    gl_FragColor = texture(tMain, vUv, uLod);
	#include <encodings_fragment>
}
`;
  var g = r(616);
  class _ {
    constructor() {
      B(
        this,
        "copyMaterial",
        new s.jyz({
          vertexShader: g.n,
          fragmentShader: l,
          blending: s.jFi,
          toneMapped: !1,
          depthWrite: !1,
          depthTest: !1,
          uniforms: {
            tMain: {
              value: null,
            },
            uLod: {
              value: 0,
            },
          },
        }),
      );
      B(this, "fullscreenMesh", new s.Kj0((0, h.lD)(), this.copyMaterial));
      B(this, "fullscreenCamera", new s.iKG(-1, 1, 1, -1, 0, 1));
    }
  }
  const A = new _();
};
