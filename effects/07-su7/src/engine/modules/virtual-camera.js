import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    _: () => g,
  });
  var s = r(591),
    h = r(25),
    l = r(879);
  class g extends s.w {
    constructor() {
      super(...arguments);
      B(this, "_finalPosition", new h.Pa4());
      B(this, "_finalRotation", new h._fP());
      B(this, "priority", 10);
      B(this, "lookAt", null);
      B(this, "follow", null);
      B(this, "fov", 45);
      B(this, "near", 0.1);
      B(this, "far", 1e3);
      B(this, "correctPosition", new h.Pa4());
      B(this, "correctRotation", new h._fP());
      B(this, "lookaheadPosition", new h.Pa4());
      B(this, "trackedObjectOffset", new h.Pa4());
      B(this, "brain");
    }
    get finalPosition() {
      return this._finalPosition.copy(this.node.position).add(this.correctPosition);
    }
    get finalRotation() {
      return this._finalRotation.copy(this.node.quaternion).multiply(this.correctRotation);
    }
    onLoad() {
      ((this.node.isCamera = !0),
        (this.brain = this.viewer.getComponent(this.viewer.camera, l.W)),
        this.brain.addCamera(this));
    }
    onDestroy() {
      this.brain.removeCamera(this);
    }
    update(m) {
      this.lookAt && this.node.lookAt(this.lookAt.position);
    }
  }
};
