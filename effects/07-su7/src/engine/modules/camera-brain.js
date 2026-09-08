import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    W: () => U,
  });
  var s = r(591),
    h = r(25),
    l = r(481),
    g;
  (function (R) {
    ((R[(R.Linear = 0)] = "Linear"),
      (R[(R.QuadraticIn = 1)] = "QuadraticIn"),
      (R[(R.QuadraticOut = 2)] = "QuadraticOut"),
      (R[(R.QuadraticInOut = 3)] = "QuadraticInOut"),
      (R[(R.CubicIn = 4)] = "CubicIn"),
      (R[(R.CubicOut = 5)] = "CubicOut"),
      (R[(R.CubicInOut = 6)] = "CubicInOut"),
      (R[(R.QuarticIn = 7)] = "QuarticIn"),
      (R[(R.QuarticOut = 8)] = "QuarticOut"),
      (R[(R.QuarticInOut = 9)] = "QuarticInOut"),
      (R[(R.QuinticIn = 10)] = "QuinticIn"),
      (R[(R.QuinticOut = 11)] = "QuinticOut"),
      (R[(R.QuinticInOut = 12)] = "QuinticInOut"),
      (R[(R.SinusoidalIn = 13)] = "SinusoidalIn"),
      (R[(R.SinusoidalOut = 14)] = "SinusoidalOut"),
      (R[(R.SinusoidalInOut = 15)] = "SinusoidalInOut"),
      (R[(R.ExponentialIn = 16)] = "ExponentialIn"),
      (R[(R.ExponentialOut = 17)] = "ExponentialOut"),
      (R[(R.ExponentialInOut = 18)] = "ExponentialInOut"),
      (R[(R.CircularIn = 19)] = "CircularIn"),
      (R[(R.CircularOut = 20)] = "CircularOut"),
      (R[(R.CircularInOut = 21)] = "CircularInOut"),
      (R[(R.ElasticIn = 22)] = "ElasticIn"),
      (R[(R.ElasticOut = 23)] = "ElasticOut"),
      (R[(R.ElasticInOut = 24)] = "ElasticInOut"),
      (R[(R.BackIn = 25)] = "BackIn"),
      (R[(R.BackOut = 26)] = "BackOut"),
      (R[(R.BackInOut = 27)] = "BackInOut"),
      (R[(R.BounceIn = 28)] = "BounceIn"),
      (R[(R.BounceOut = 29)] = "BounceOut"),
      (R[(R.BounceInOut = 30)] = "BounceInOut"));
  })(g || (g = {}));
  const _ = [
    l.Easing.Linear.None,
    l.Easing.Quadratic.In,
    l.Easing.Quadratic.Out,
    l.Easing.Quadratic.InOut,
    l.Easing.Cubic.In,
    l.Easing.Cubic.Out,
    l.Easing.Cubic.InOut,
    l.Easing.Quintic.In,
    l.Easing.Quadratic.Out,
    l.Easing.Quadratic.InOut,
    l.Easing.Quintic.In,
    l.Easing.Quintic.Out,
    l.Easing.Quintic.InOut,
    l.Easing.Sinusoidal.In,
    l.Easing.Sinusoidal.Out,
    l.Easing.Sinusoidal.InOut,
    l.Easing.Exponential.In,
    l.Easing.Exponential.Out,
    l.Easing.Exponential.InOut,
    l.Easing.Circular.In,
    l.Easing.Circular.Out,
    l.Easing.Circular.InOut,
    l.Easing.Elastic.In,
    l.Easing.Elastic.Out,
    l.Easing.Elastic.InOut,
    l.Easing.Back.In,
    l.Easing.Back.Out,
    l.Easing.Back.InOut,
    l.Easing.Bounce.In,
    l.Easing.Bounce.Out,
    l.Easing.Bounce.InOut,
  ];
  class A {
    constructor() {
      B(this, "style", g.QuadraticInOut);
      B(this, "time", 4);
    }
  }
  const { clamp: m, lerp: D } = h.MathUtils;
  class U extends s.w {
    constructor() {
      super(...arguments);
      B(this, "_vcam", null);
      B(this, "_vcamSolo", null);
      B(this, "_vcams", []);
      B(this, "_lerpTime", 0);
      B(this, "brainBlend", new A());
    }
    get vcam() {
      return this._vcam;
    }
    get vcams() {
      return this._vcams;
    }
    update(ce) {
      let xe = this.getActiveCamera();
      if (xe != null) {
        for (let Se of this._vcams) Se.enabled = Se === xe;
        if (this._lerpTime < this.brainBlend.time) {
          this._lerpTime += ce;
          let Se = m(this._lerpTime / this.brainBlend.time, 0, 1),
            $ = _[this.brainBlend.style];
          ($ && (Se = $(Se)), this._lerpToMainCamera(xe, Se));
        } else this._lerpToMainCamera(xe, 1);
      }
    }
    activeCamera(ce, xe = 4) {
      this._vcamSolo !== ce &&
        ((this._vcamSolo = ce), (this._lerpTime = 0), (this.brainBlend.time = xe));
    }
    addCamera(ce) {
      this._vcams.indexOf(ce) === -1 && this._vcams.push(ce);
    }
    removeCamera(ce) {
      let xe = this._vcams.indexOf(ce);
      xe !== -1 && this._vcams.splice(xe, 1);
    }
    getActiveCamera() {
      return (
        this._vcamSolo ||
        this._vcams.filter((ce) => ce.enabled).sort((ce, xe) => xe.priority - ce.priority)[0]
      );
    }
    _lerpToMainCamera(ce, xe) {
      let Se = this.viewer.camera,
        $ = ce;
      (Se.position.lerp($.finalPosition, xe),
        Se.quaternion.slerp($.finalRotation, xe),
        (Se.fov = D(Se.fov, $.fov, xe)),
        (Se.near = D(Se.near, $.near, xe)),
        (Se.far = D(Se.far, $.far, xe)),
        (Se.fov != $.fov || Se.near != $.near || Se.far != $.far) && Se.updateProjectionMatrix());
    }
  }
};
