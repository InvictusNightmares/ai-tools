import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    Oe: () => l,
    lD: () => g,
    lK: () => D,
    tQ: () => A,
  });
  var s = r(25),
    h = r(861);
  function l(U, R, ne) {
    let ce = {};
    U.traverse((q) => {
      var N;
      if (q.visible && q.isMesh && q.geometry) {
        if (ne && ne(q)) return;
        let ie = q.geometry.uuid + ((N = q.material) == null ? void 0 : N.name);
        (ce[ie] == null &&
          (ce[ie] = {
            geometry: q.geometry,
            material: q.material,
            group: [],
          }),
          ce[ie].group.push(q));
      }
    });
    let xe = 0,
      Se = 0,
      $ = new s.ZAu();
    for (let q in ce) {
      let N = ce[q],
        { geometry: ie, material: _e, group: Pe } = N,
        Be = new s.SPe(ie, _e, Pe.length);
      for (let Re = Pe.length; Re--;)
        (Pe[Re].updateWorldMatrix(!0, !1), Be.setMatrixAt(Re, Pe[Re].matrixWorld));
      ((0, h.$p)(Be, R), $.add(Be), Se++, (xe += Pe.length));
    }
    return (console.log("makeInstanced", "instance", Se, "count", xe), $);
  }
  function g() {
    let U = new s.u9r();
    return (
      U.setAttribute("position", new s.a$l([-1, 3, 0, -1, -1, 0, 3, -1, 0], 3)),
      U.setAttribute("uv", new s.a$l([0, 2, 0, 0, 2, 0], 2)),
      U
    );
  }
  const _ = [
    "alphaMap",
    "aoMap",
    "bumpMap",
    "displacementMap",
    "emissiveMap",
    "envMap",
    "lightMap",
    "metalnessMap",
    "normalMap",
    "roughnessMap",
    "specularMap",
  ];
  function A(
    U,
    R = {
      meshes: [],
      materials: {},
      textures: {},
    },
  ) {
    return (
      U.traverse((ne) => {
        if (ne instanceof s.Kj0) {
          const ce = ne.material;
          (R.meshes.push(ne), (R.materials[ce.name] = ce));
          let xe = null;
          for (let Se of _) ((xe = ce[Se]), xe && (R.textures[xe.uuid] = xe));
        }
      }),
      R
    );
  }
  const m = ["top", "bottom", "left", "right", "near", "far"];
  function D(U, R) {
    const ne = U.camera;
    for (let ce = 0; ce < R.length && ce < 6; ce++) ne[m[ce]] = R[ce];
    return (R.length > 6 && (U.bias = R[6]), R.length > 8 && U.mapSize.set(R[7], R[8]), U);
  }
};
