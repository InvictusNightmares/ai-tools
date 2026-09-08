import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    U: () => h,
  });
  var s = r(25);
  function h(l, g) {
    let _ = l * l,
      A = 2 * Math.PI * _,
      m = Math.pow(16, g) * 1.386294361,
      D = A * (Math.pow(4, g) + A);
    return s.MathUtils.clamp01(m / D);
  }
};
