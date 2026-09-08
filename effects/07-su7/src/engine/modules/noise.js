import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    H: () => h,
  });
  const { floor: s } = Math,
    l = class l {
      static Noise(_, A, m) {
        let D = l._Fade,
          U = l._Grad,
          R = l._Lerp,
          ne = l._Permutation;
        if (A !== void 0 && m !== void 0) {
          let ce = s(_),
            xe = s(A),
            Se = s(m),
            $ = ce & 255,
            q = xe & 255,
            N = Se & 255;
          ((_ -= ce), (A -= xe), (m -= Se));
          let ie = D(_),
            _e = D(A),
            Pe = D(m),
            Be = ne[$] + q,
            Re = ne[Be] + N,
            ct = ne[Be + 1] + N,
            et = ne[$ + 1] + q,
            Ze = ne[et] + N,
            Nt = ne[et + 1] + N;
          return R(
            Pe,
            R(
              _e,
              R(ie, U(ne[Re], _, A, m), U(ne[Ze], _ - 1, A, m)),
              R(ie, U(ne[ct], _, A - 1, m), U(ne[Nt], _ - 1, A - 1, m)),
            ),
            R(
              _e,
              R(ie, U(ne[Re + 1], _, A, m - 1), U(ne[Ze + 1], _ - 1, A, m - 1)),
              R(ie, U(ne[ct + 1], _, A - 1, m - 1), U(ne[Nt + 1], _ - 1, A - 1, m - 1)),
            ),
          );
        } else if (A !== void 0) {
          let ce = s(_),
            xe = s(A),
            Se = ce & 255,
            $ = xe & 255;
          ((_ -= ce), (A -= xe));
          let q = D(_),
            N = D(A),
            ie = (ne[Se] + $) & 255,
            _e = (ne[Se + 1] + $) & 255;
          return R(
            N,
            R(q, U(ne[ie], _, A), U(ne[_e], _ - 1, A)),
            R(q, U(ne[ie + 1], _, A - 1), U(ne[_e + 1], _ - 1, A - 1)),
          );
        } else {
          let ce = s(_),
            xe = ce & 255;
          _ -= ce;
          let Se = D(_);
          return R(Se, U(ne[xe], _), U(ne[xe + 1], _ - 1));
        }
      }
      static Fbm(_, A, m, D) {
        let U = 0,
          R = 0.5,
          ne = l.Noise;
        if (m !== void 0 && D !== void 0)
          for (let ce = 0; ce < _; ce++)
            ((U += R * ne(A, m, D)), (A *= 2), (m *= 2), (D *= 2), (R *= 0.5));
        else if (m !== void 0)
          for (let ce = 0; ce < _; ce++) ((U += R * ne(A, m)), (A *= 2), (m *= 2), (R *= 0.5));
        else for (let ce = 0; ce < _; ce++) ((U += R * ne(A)), (A *= 2), (R *= 0.5));
        return U;
      }
      static _Fade(_) {
        return _ * _ * _ * (_ * (_ * 6 - 15) + 10);
      }
      static _Lerp(_, A, m) {
        return A + _ * (m - A);
      }
      static _Grad(_, A, m, D) {
        if (m !== void 0 && D !== void 0) {
          let U = _ & 15,
            R = U < 8 ? A : m,
            ne = U < 4 ? m : U == 12 || U == 14 ? A : D;
          return (U & 1 ? -R : R) + (U & 2 ? -ne : ne);
        } else return m !== void 0 ? (_ & 1 ? -A : A) + (_ & 2 ? -m : m) : _ & 1 ? -A : A;
      }
    };
  B(
    l,
    "_Permutation",
    [
      151, 160, 137, 91, 90, 15, 131, 13, 201, 95, 96, 53, 194, 233, 7, 225, 140, 36, 103, 30, 69,
      142, 8, 99, 37, 240, 21, 10, 23, 190, 6, 148, 247, 120, 234, 75, 0, 26, 197, 62, 94, 252, 219,
      203, 117, 35, 11, 32, 57, 177, 33, 88, 237, 149, 56, 87, 174, 20, 125, 136, 171, 168, 68, 175,
      74, 165, 71, 134, 139, 48, 27, 166, 77, 146, 158, 231, 83, 111, 229, 122, 60, 211, 133, 230,
      220, 105, 92, 41, 55, 46, 245, 40, 244, 102, 143, 54, 65, 25, 63, 161, 1, 216, 80, 73, 209,
      76, 132, 187, 208, 89, 18, 169, 200, 196, 135, 130, 116, 188, 159, 86, 164, 100, 109, 198,
      173, 186, 3, 64, 52, 217, 226, 250, 124, 123, 5, 202, 38, 147, 118, 126, 255, 82, 85, 212,
      207, 206, 59, 227, 47, 16, 58, 17, 182, 189, 28, 42, 223, 183, 170, 213, 119, 248, 152, 2, 44,
      154, 163, 70, 221, 153, 101, 155, 167, 43, 172, 9, 129, 22, 39, 253, 19, 98, 108, 110, 79,
      113, 224, 232, 178, 185, 112, 104, 218, 246, 97, 228, 251, 34, 242, 193, 238, 210, 144, 12,
      191, 179, 162, 241, 81, 51, 145, 235, 249, 14, 239, 107, 49, 192, 214, 31, 181, 199, 106, 157,
      184, 84, 204, 176, 115, 121, 50, 45, 127, 4, 150, 254, 138, 236, 205, 93, 222, 114, 67, 29,
      24, 72, 243, 141, 128, 195, 78, 66, 215, 61, 156, 180, 151,
    ],
  );
  let h = l;
};
