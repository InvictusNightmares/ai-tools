import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    Cb: () => s,
    HO: () => h,
    jf: () => l,
  });
  function s(g = {}) {
    return function (_, A) {
      (_.hasOwnProperty("__properties") ||
        (_.__properties = Object.assign({}, _.__proto__.__properties)),
        (_.__properties[A] = g));
    };
  }
  function h(...g) {
    return function (_) {
      let A = _.prototype;
      (A.__dependencies == null && (A.__dependencies = []), A.__dependencies.push(...g));
    };
  }
  function l(g = "", _ = 0, A = !1) {
    return function (m) {
      let D = m.prototype;
      D.__display == null &&
        (D.__display = {
          name: g || m.name || m.constructor.name,
          order: _,
          root: A,
        });
    };
  }
};
