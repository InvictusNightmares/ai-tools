import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    $S: () => l,
    EK: () => _,
    NB: () => h,
    Wr: () => g,
  });
  var s = r(322);
  function h(A, m, D, U, R) {
    s.c.fullscreenMesh.material = D;
    const ne = A.getRenderTarget();
    (A.setRenderTarget(m, R, U),
      A.render(s.c.fullscreenMesh, s.c.fullscreenCamera),
      A.setRenderTarget(ne));
  }
  function l(A, m) {
    if (Array.isArray(m)) for (let D of m) A.initTexture(D);
    else A.initTexture(m);
  }
  function g(A, m, D, U) {
    ((s.c.fullscreenMesh.material = U), A.compile(s.c.fullscreenMesh, D, m));
  }
  function _(A, m, D, U) {
    A.compile(U, D, m);
  }
};
