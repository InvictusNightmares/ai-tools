import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n) => {
  Object.defineProperty(n, "__esModule", {
    value: !0,
  });
  var r = {
      Linear: {
        None: function (N) {
          return N;
        },
      },
      Quadratic: {
        In: function (N) {
          return N * N;
        },
        Out: function (N) {
          return N * (2 - N);
        },
        InOut: function (N) {
          return (N *= 2) < 1 ? 0.5 * N * N : -0.5 * (--N * (N - 2) - 1);
        },
      },
      Cubic: {
        In: function (N) {
          return N * N * N;
        },
        Out: function (N) {
          return --N * N * N + 1;
        },
        InOut: function (N) {
          return (N *= 2) < 1 ? 0.5 * N * N * N : 0.5 * ((N -= 2) * N * N + 2);
        },
      },
      Quartic: {
        In: function (N) {
          return N * N * N * N;
        },
        Out: function (N) {
          return 1 - --N * N * N * N;
        },
        InOut: function (N) {
          return (N *= 2) < 1 ? 0.5 * N * N * N * N : -0.5 * ((N -= 2) * N * N * N - 2);
        },
      },
      Quintic: {
        In: function (N) {
          return N * N * N * N * N;
        },
        Out: function (N) {
          return --N * N * N * N * N + 1;
        },
        InOut: function (N) {
          return (N *= 2) < 1 ? 0.5 * N * N * N * N * N : 0.5 * ((N -= 2) * N * N * N * N + 2);
        },
      },
      Sinusoidal: {
        In: function (N) {
          return 1 - Math.cos((N * Math.PI) / 2);
        },
        Out: function (N) {
          return Math.sin((N * Math.PI) / 2);
        },
        InOut: function (N) {
          return 0.5 * (1 - Math.cos(Math.PI * N));
        },
      },
      Exponential: {
        In: function (N) {
          return N === 0 ? 0 : Math.pow(1024, N - 1);
        },
        Out: function (N) {
          return N === 1 ? 1 : 1 - Math.pow(2, -10 * N);
        },
        InOut: function (N) {
          return N === 0
            ? 0
            : N === 1
              ? 1
              : (N *= 2) < 1
                ? 0.5 * Math.pow(1024, N - 1)
                : 0.5 * (-Math.pow(2, -10 * (N - 1)) + 2);
        },
      },
      Circular: {
        In: function (N) {
          return 1 - Math.sqrt(1 - N * N);
        },
        Out: function (N) {
          return Math.sqrt(1 - --N * N);
        },
        InOut: function (N) {
          return (N *= 2) < 1
            ? -0.5 * (Math.sqrt(1 - N * N) - 1)
            : 0.5 * (Math.sqrt(1 - (N -= 2) * N) + 1);
        },
      },
      Elastic: {
        In: function (N) {
          return N === 0
            ? 0
            : N === 1
              ? 1
              : -Math.pow(2, 10 * (N - 1)) * Math.sin((N - 1.1) * 5 * Math.PI);
        },
        Out: function (N) {
          return N === 0
            ? 0
            : N === 1
              ? 1
              : Math.pow(2, -10 * N) * Math.sin((N - 0.1) * 5 * Math.PI) + 1;
        },
        InOut: function (N) {
          return N === 0
            ? 0
            : N === 1
              ? 1
              : ((N *= 2),
                N < 1
                  ? -0.5 * Math.pow(2, 10 * (N - 1)) * Math.sin((N - 1.1) * 5 * Math.PI)
                  : 0.5 * Math.pow(2, -10 * (N - 1)) * Math.sin((N - 1.1) * 5 * Math.PI) + 1);
        },
      },
      Back: {
        In: function (N) {
          var ie = 1.70158;
          return N * N * ((ie + 1) * N - ie);
        },
        Out: function (N) {
          var ie = 1.70158;
          return --N * N * ((ie + 1) * N + ie) + 1;
        },
        InOut: function (N) {
          var ie = 2.5949095;
          return (N *= 2) < 1
            ? 0.5 * (N * N * ((ie + 1) * N - ie))
            : 0.5 * ((N -= 2) * N * ((ie + 1) * N + ie) + 2);
        },
      },
      Bounce: {
        In: function (N) {
          return 1 - r.Bounce.Out(1 - N);
        },
        Out: function (N) {
          return N < 1 / 2.75
            ? 7.5625 * N * N
            : N < 2 / 2.75
              ? 7.5625 * (N -= 1.5 / 2.75) * N + 0.75
              : N < 2.5 / 2.75
                ? 7.5625 * (N -= 2.25 / 2.75) * N + 0.9375
                : 7.5625 * (N -= 2.625 / 2.75) * N + 0.984375;
        },
        InOut: function (N) {
          return N < 0.5 ? r.Bounce.In(N * 2) * 0.5 : r.Bounce.Out(N * 2 - 1) * 0.5 + 0.5;
        },
      },
    },
    s;
  typeof self > "u" && typeof process < "u" && process.hrtime
    ? (s = function () {
        var N = process.hrtime();
        return N[0] * 1e3 + N[1] / 1e6;
      })
    : typeof self < "u" && self.performance !== void 0 && self.performance.now !== void 0
      ? (s = self.performance.now.bind(self.performance))
      : Date.now !== void 0
        ? (s = Date.now)
        : (s = function () {
            return new Date().getTime();
          });
  function h() {
    return s() * 0.001;
  }
  var l = (function () {
      function N() {
        ((this._tweens = {}), (this._tweensAddedDuringUpdate = {}));
      }
      return (
        (N.prototype.getAll = function () {
          var ie = this;
          return Object.keys(this._tweens).map(function (_e) {
            return ie._tweens[_e];
          });
        }),
        (N.prototype.removeAll = function () {
          this._tweens = {};
        }),
        (N.prototype.add = function (ie) {
          ((this._tweens[ie.getId()] = ie), (this._tweensAddedDuringUpdate[ie.getId()] = ie));
        }),
        (N.prototype.remove = function (ie) {
          (delete this._tweens[ie.getId()], delete this._tweensAddedDuringUpdate[ie.getId()]);
        }),
        (N.prototype.update = function (ie, _e) {
          (ie === void 0 && (ie = h()), _e === void 0 && (_e = !1));
          var Pe = Object.keys(this._tweens);
          if (Pe.length === 0) return !1;
          for (; Pe.length > 0;) {
            this._tweensAddedDuringUpdate = {};
            for (var Be = 0; Be < Pe.length; Be++) {
              var Re = this._tweens[Pe[Be]],
                ct = !_e;
              Re && Re.update(ie, ct) === !1 && !_e && delete this._tweens[Pe[Be]];
            }
            Pe = Object.keys(this._tweensAddedDuringUpdate);
          }
          return !0;
        }),
        N
      );
    })(),
    g = {
      Linear: function (N, ie) {
        var _e = N.length - 1,
          Pe = _e * ie,
          Be = Math.floor(Pe),
          Re = g.Utils.Linear;
        return ie < 0
          ? Re(N[0], N[1], Pe)
          : ie > 1
            ? Re(N[_e], N[_e - 1], _e - Pe)
            : Re(N[Be], N[Be + 1 > _e ? _e : Be + 1], Pe - Be);
      },
      Bezier: function (N, ie) {
        for (
          var _e = 0, Pe = N.length - 1, Be = Math.pow, Re = g.Utils.Bernstein, ct = 0;
          ct <= Pe;
          ct++
        )
          _e += Be(1 - ie, Pe - ct) * Be(ie, ct) * N[ct] * Re(Pe, ct);
        return _e;
      },
      CatmullRom: function (N, ie) {
        var _e = N.length - 1,
          Pe = _e * ie,
          Be = Math.floor(Pe),
          Re = g.Utils.CatmullRom;
        return N[0] === N[_e]
          ? (ie < 0 && (Be = Math.floor((Pe = _e * (1 + ie)))),
            Re(N[(Be - 1 + _e) % _e], N[Be], N[(Be + 1) % _e], N[(Be + 2) % _e], Pe - Be))
          : ie < 0
            ? N[0] - (Re(N[0], N[0], N[1], N[1], -Pe) - N[0])
            : ie > 1
              ? N[_e] - (Re(N[_e], N[_e], N[_e - 1], N[_e - 1], Pe - _e) - N[_e])
              : Re(
                  N[Be ? Be - 1 : 0],
                  N[Be],
                  N[_e < Be + 1 ? _e : Be + 1],
                  N[_e < Be + 2 ? _e : Be + 2],
                  Pe - Be,
                );
      },
      Utils: {
        Linear: function (N, ie, _e) {
          return (ie - N) * _e + N;
        },
        Bernstein: function (N, ie) {
          var _e = g.Utils.Factorial;
          return _e(N) / _e(ie) / _e(N - ie);
        },
        Factorial: (function () {
          var N = [1];
          return function (ie) {
            var _e = 1;
            if (N[ie]) return N[ie];
            for (var Pe = ie; Pe > 1; Pe--) _e *= Pe;
            return ((N[ie] = _e), _e);
          };
        })(),
        CatmullRom: function (N, ie, _e, Pe, Be) {
          var Re = (_e - N) * 0.5,
            ct = (Pe - ie) * 0.5,
            et = Be * Be,
            Ze = Be * et;
          return (
            (2 * ie - 2 * _e + Re + ct) * Ze + (-3 * ie + 3 * _e - 2 * Re - ct) * et + Re * Be + ie
          );
        },
      },
    },
    _ = (function () {
      function N() {}
      return (
        (N.nextId = function () {
          return N._nextId++;
        }),
        (N._nextId = 0),
        N
      );
    })(),
    A = new l(),
    m = (function () {
      function N(ie, _e) {
        (_e === void 0 && (_e = A),
          (this._object = ie),
          (this._group = _e),
          (this._isPaused = !1),
          (this._pauseStart = 0),
          (this._valuesStart = {}),
          (this._valuesEnd = {}),
          (this._valuesStartRepeat = {}),
          (this._duration = 0),
          (this._initialRepeat = 0),
          (this._repeat = 0),
          (this._yoyo = !1),
          (this._isPlaying = !1),
          (this._reversed = !1),
          (this._delayTime = 0),
          (this._startTime = 0),
          (this._easingFunction = r.Linear.None),
          (this._interpolationFunction = g.Linear),
          (this._chainedTweens = []),
          (this._onStartCallbackFired = !1),
          (this._id = _.nextId()),
          (this._isChainStopped = !1),
          (this._goToEnd = !1),
          (this._headTween = null),
          (this._tailTween = null),
          (this._headStart = !1));
      }
      return (
        (N.prototype.getId = function () {
          return this._id;
        }),
        (N.prototype.isPlaying = function () {
          return this._isPlaying;
        }),
        (N.prototype.isPaused = function () {
          return this._isPaused;
        }),
        (N.prototype.duration = function (ie) {
          return ((this._duration = ie), this);
        }),
        (N.prototype.start = function (ie) {
          if (this._isPlaying) return this;
          if (
            (this._group && this._group.add(this),
            (this._repeat = this._initialRepeat),
            this._reversed)
          ) {
            this._reversed = !1;
            for (var _e in this._valuesStartRepeat)
              (this._swapEndStartRepeatValues(_e),
                (this._valuesStart[_e] = this._valuesStartRepeat[_e]));
          }
          return (
            (this._isPlaying = !0),
            (this._isPaused = !1),
            (this._onStartCallbackFired = !1),
            (this._isChainStopped = !1),
            (this._startTime =
              ie !== void 0 ? (typeof ie == "string" ? h() + parseFloat(ie) : ie) : h()),
            (this._startTime += this._delayTime),
            this._setupProperties(
              this._object,
              this._valuesStart,
              this._valuesEnd,
              this._valuesStartRepeat,
            ),
            this
          );
        }),
        (N.prototype._setupProperties = function (ie, _e, Pe, Be) {
          for (var Re in Pe) {
            var ct = ie[Re],
              et = Array.isArray(ct),
              Ze = et ? "array" : typeof ct,
              Nt = !et && Array.isArray(Pe[Re]);
            if (!(Ze === "undefined" || Ze === "function")) {
              if (Nt) {
                var Bt = Pe[Re];
                if (Bt.length === 0) continue;
                ((Bt = Bt.map(this._handleRelativeValue.bind(this, ct))),
                  (Pe[Re] = [ct].concat(Bt)));
              }
              if ((Ze === "object" || et) && ct && !Nt) {
                _e[Re] = et ? [] : {};
                for (var en in ct) _e[Re][en] = ct[en];
                ((Be[Re] = et ? [] : {}), this._setupProperties(ct, _e[Re], Pe[Re], Be[Re]));
              } else
                (typeof _e[Re] > "u" && (_e[Re] = ct),
                  et || (_e[Re] *= 1),
                  Nt ? (Be[Re] = Pe[Re].slice().reverse()) : (Be[Re] = _e[Re] || 0));
            }
          }
        }),
        (N.prototype.stop = function () {
          return (
            this._isChainStopped || ((this._isChainStopped = !0), this.stopChainedTweens()),
            this._isPlaying
              ? (this._group && this._group.remove(this),
                (this._isPlaying = !1),
                (this._isPaused = !1),
                this._onStopCallback && this._onStopCallback(this._object),
                this)
              : this
          );
        }),
        (N.prototype.end = function () {
          return ((this._goToEnd = !0), this.update(1 / 0), this);
        }),
        (N.prototype.pause = function (ie) {
          return (
            ie === void 0 && (ie = h()),
            this._isPaused || !this._isPlaying
              ? this
              : ((this._isPaused = !0),
                (this._pauseStart = ie),
                this._group && this._group.remove(this),
                this)
          );
        }),
        (N.prototype.resume = function (ie) {
          return (
            ie === void 0 && (ie = h()),
            !this._isPaused || !this._isPlaying
              ? this
              : ((this._isPaused = !1),
                (this._startTime += ie - this._pauseStart),
                (this._pauseStart = 0),
                this._group && this._group.add(this),
                this)
          );
        }),
        (N.prototype.stopChainedTweens = function () {
          for (var ie = 0, _e = this._chainedTweens.length; ie < _e; ie++)
            this._chainedTweens[ie].stop();
          return ((this._chainedTweens = []), this);
        }),
        (N.prototype.group = function (ie) {
          return ((this._group = ie), this);
        }),
        (N.prototype.call = function (ie) {
          return ((this._onFinishCallback = ie), this);
        }),
        (N.prototype.from = function (ie) {
          return ((this._valuesStart = Object.create(ie)), this);
        }),
        (N.prototype.to = function (ie, _e) {
          return (
            (this._valuesEnd = Object.create(ie)),
            _e !== void 0 && (this._duration = _e),
            (this._chainedTween = this),
            this
          );
        }),
        (N.prototype.delay = function (ie) {
          return ((this._delayTime = ie), this);
        }),
        (N.prototype.union = function (ie, _e) {
          return (
            (this._headTween = ie),
            (this._tailTween = _e.chain(this)),
            (this._headStart = !0),
            this
          );
        }),
        (N.prototype.repeat = function (ie) {
          return ((this._initialRepeat = ie), (this._repeat = ie), this);
        }),
        (N.prototype.repeatDelay = function (ie) {
          return ((this._repeatDelayTime = ie), this);
        }),
        (N.prototype.yoyo = function (ie) {
          return ((this._yoyo = ie), this);
        }),
        (N.prototype.easing = function (ie) {
          return ((this._easingFunction = ie), this);
        }),
        (N.prototype.interpolation = function (ie) {
          return ((this._interpolationFunction = ie), this);
        }),
        (N.prototype.chain = function () {
          for (var ie = [], _e = 0; _e < arguments.length; _e++) ie[_e] = arguments[_e];
          return ((this._chainedTweens = ie), this);
        }),
        (N.prototype.unchain = function () {
          for (var ie = 0; ie < arguments.length; ie++) {
            let _e = this._chainedTweens.findIndex((Pe) => Pe == arguments[ie]);
            _e > -1 && this._chainedTweens.splice(_e, 1);
          }
          return this;
        }),
        (N.prototype.onStart = function (ie) {
          return ((this._onStartCallback = ie), this);
        }),
        (N.prototype.onUpdate = function (ie) {
          return ((this._onUpdateCallback = ie), this);
        }),
        (N.prototype.onRepeat = function (ie) {
          return ((this._onRepeatCallback = ie), this);
        }),
        (N.prototype.onComplete = function (ie) {
          return ((this._onCompleteCallback = ie), this);
        }),
        (N.prototype.onStop = function (ie) {
          return ((this._onStopCallback = ie), this);
        }),
        (N.prototype.update = function (ie, _e) {
          if ((ie === void 0 && (ie = h()), _e === void 0 && (_e = !0), this._isPaused)) return !0;
          var Pe,
            Be,
            Re = this._startTime + this._duration;
          if (!this._goToEnd && !this._isPlaying) {
            if (ie > Re) return !1;
            _e && this.start(ie);
          }
          if (((this._goToEnd = !1), ie < this._startTime)) return !0;
          (this._onStartCallbackFired === !1 &&
            (this._onStartCallback && this._onStartCallback(this._object),
            (this._onStartCallbackFired = !0)),
            (Be = (ie - this._startTime) / this._duration),
            (Be = this._duration === 0 || Be > 1 ? 1 : Be));
          var ct = this._easingFunction(Be);
          if (
            (this._updateProperties(this._object, this._valuesStart, this._valuesEnd, ct),
            this._onUpdateCallback && this._onUpdateCallback(this._object, Be),
            Be === 1)
          ) {
            if (
              (this._onFinishCallback && this._onFinishCallback(this._object),
              this._headTween && this._headStart)
            )
              return (
                this._headTween.start(this._startTime + this._duration),
                (this._headStart = !1),
                (this._isPlaying = !1),
                !1
              );
            if (this._repeat > 0) {
              isFinite(this._repeat) && this._repeat--;
              for (Pe in this._valuesStartRepeat)
                (!this._yoyo &&
                  typeof this._valuesEnd[Pe] == "string" &&
                  (this._valuesStartRepeat[Pe] =
                    this._valuesStartRepeat[Pe] + parseFloat(this._valuesEnd[Pe])),
                  this._yoyo && this._swapEndStartRepeatValues(Pe),
                  (this._valuesStart[Pe] = this._valuesStartRepeat[Pe]));
              return (
                this._yoyo && (this._reversed = !this._reversed),
                this._repeatDelayTime !== void 0
                  ? (this._startTime = ie + this._repeatDelayTime)
                  : (this._startTime = ie + this._delayTime),
                this._onRepeatCallback && this._onRepeatCallback(this._object),
                this._headTween && ((this._headStart = !0), (this._initialRepeat = this._repeat)),
                !0
              );
            } else {
              (this._tailTween && this._tailTween.unchain(this),
                this._onCompleteCallback && this._onCompleteCallback(this._object));
              for (var et = 0, Ze = this._chainedTweens.length; et < Ze; et++)
                this._chainedTweens[et].start(this._startTime + this._duration);
              return ((this._isPlaying = !1), !1);
            }
          }
          return !0;
        }),
        (N.prototype._updateProperties = function (ie, _e, Pe, Be) {
          for (var Re in Pe)
            if (_e[Re] !== void 0) {
              var ct = _e[Re] || 0,
                et = Pe[Re],
                Ze = Array.isArray(ie[Re]),
                Nt = Array.isArray(et),
                Bt = !Ze && Nt;
              if (Bt) ie[Re] = this._interpolationFunction(et, Be);
              else if (typeof et == "object" && et) {
                this._updateProperties(ie[Re], ct, et, Be);
                let en = Object.getOwnPropertyDescriptor(ie, Re);
                en && en.set && (ie[Re] = ie[Re]);
              } else
                ((et = this._handleRelativeValue(ct, et)),
                  typeof et == "number" && (ie[Re] = ct + (et - ct) * Be));
            }
        }),
        (N.prototype._handleRelativeValue = function (ie, _e) {
          return typeof _e != "string"
            ? _e
            : _e.charAt(0) === "+" || _e.charAt(0) === "-"
              ? ie + parseFloat(_e)
              : parseFloat(_e);
        }),
        (N.prototype._swapEndStartRepeatValues = function (ie) {
          var _e = this._valuesStartRepeat[ie],
            Pe = this._valuesEnd[ie];
          (typeof Pe == "string"
            ? (this._valuesStartRepeat[ie] = this._valuesStartRepeat[ie] + parseFloat(Pe))
            : (this._valuesStartRepeat[ie] = this._valuesEnd[ie]),
            (this._valuesEnd[ie] = _e));
        }),
        N
      );
    })(),
    D = "18.6.4",
    U = _.nextId,
    R = A,
    ne = R.getAll.bind(R),
    ce = R.removeAll.bind(R),
    xe = R.add.bind(R),
    Se = R.remove.bind(R),
    $ = R.update.bind(R),
    q = {
      Easing: r,
      Group: l,
      Interpolation: g,
      now: h,
      Sequence: _,
      nextId: U,
      Tween: m,
      VERSION: D,
      getAll: ne,
      removeAll: ce,
      add: xe,
      remove: Se,
      update: $,
    };
  ((n.Easing = r),
    (n.Group = l),
    (n.Interpolation = g),
    (n.Sequence = _),
    (n.Tween = m),
    (n.VERSION = D),
    (n.add = xe),
    (n.default = q),
    (n.getAll = ne),
    (n.nextId = U),
    (n.now = h),
    (n.remove = Se),
    (n.removeAll = ce),
    (n.update = $));
};
