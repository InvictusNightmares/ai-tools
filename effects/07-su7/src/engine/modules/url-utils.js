import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    BR: () => g,
    G: () => m,
    I_: () => h,
    J1: () => l,
    bk: () => _,
    oG: () => s,
  });
  function s(D) {
    let U = D.split(".");
    return U.length > 1 ? U.pop() : "";
  }
  function h(D) {
    let U = D.lastIndexOf("/");
    return U !== -1 ? D.substring(0, U) : "";
  }
  function l(D, U) {
    let R = D.split("/").pop();
    return U ? R.replace("." + U, "") : R;
  }
  function g(D) {
    let U = "",
      R = null,
      ne = "";
    return (
      typeof File < "u" && D instanceof File
        ? ((U = D.name), (ne = s(U)), (R = D))
        : typeof D == "object"
          ? ((U = D.mainFile.name), (ne = s(U)), (R = D))
          : ((U += D), (ne = s(U))),
      {
        url: U,
        file: R,
        ext: ne,
      }
    );
  }
  function _(D, U) {
    let R = [D];
    for (let ne in U) U[ne] !== void 0 && R.push(ne + "=" + U[ne]);
    return R.join(",");
  }
  const A = [
    "flipY",
    "mapping",
    "wrapS",
    "wrapT",
    "dataType",
    "magFilter",
    "minFilter",
    "format",
    "anisotropy",
    "encoding",
    "repeat",
  ];
  function m(D) {
    let U = {};
    for (let R of A) D[R] !== void 0 && (R === "dataType" ? (U.type = D[R]) : (U[R] = D[R]));
    return U;
  }
};
