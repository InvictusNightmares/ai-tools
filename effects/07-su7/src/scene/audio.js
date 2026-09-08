import { Component, tO, Tweening } from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
import { resourceConfig } from "./../config/resources.js";
import { events, ShowState } from "./../state/events.js";
class AudioController extends Component {
  constructor() {
    super(...arguments);
    B(this, "_sound");
    B(this, "_beatID", -1);
    B(this, "_scan0ID", -1);
    B(this, "_scan0Changed", !1);
    B(this, "_bubuID", -1);
  }
  onLoad() {
    ((this._sound = new tO({
      src: [resourceConfig.autoURL("res/audios/bgm2.mp3")],
      sprite: {
        melody: [0, 14534, !0],
        beat: [14535, 10900, !0],
        click: [25500, 370],
        scan0: [26e3, 734],
        scan1: [26867, 734],
        ka: [27700, 367],
        bubu: [28200, 1300, !0],
      },
    })),
      events.on(events.PLAY_BGM, () => {
        (this._sound.play("melody"),
          (this._beatID = this._sound.play("beat")),
          (this._bubuID = this._sound.play("bubu")),
          this._sound.volume(0, this._bubuID));
      }),
      events.on(events.PLAY_SFX, (r) => {
        this._sound.play(r);
      }),
      events.on(events.MUTE, (r) => {
        this._sound.mute(r);
      }),
      events.on(events.PRESSED_STATE_CHANGED, (r, s) => {
        (s === ShowState.State1 &&
          (Tweening.TweenManager.KillTweensOf(this._sound),
          r
            ? (events.currentColorIndex === "11" &&
                Tweening.TweenManager.Timeline(this._sound)
                  .delay(1)
                  .call(() => {
                    this._sound.fade(this._sound.volume(this._bubuID), 0.8, 1e3, this._bubuID);
                  })
                  .start(),
              this._sound.fade(this._sound.volume(this._beatID), 0.3, 1e3, this._beatID))
            : (this._sound.fade(this._sound.volume(this._beatID), 1, 1e3, this._beatID),
              this._sound.fade(this._sound.volume(this._bubuID), 0, 1e3, this._bubuID))),
          s === ShowState.State2 &&
            (Tweening.TweenManager.KillTweensOf(this._sound),
            r &&
              Tweening.TweenManager.Timeline(this._sound)
                .delay(0.3)
                .call(() => {
                  this._sound.play("boom");
                })
                .start()),
          s === ShowState.State3 &&
            (Tweening.TweenManager.KillTweensOf(this._sound),
            r
              ? Tweening.TweenManager.Timeline(this._sound)
                  .delay(0.3)
                  .call(() => {
                    ((this._scan0ID = this._sound.play("scan0")), (this._scan0Changed = !0));
                  })
                  .start()
              : this._scan0Changed &&
                ((this._scan0Changed = !1),
                this._sound.stop(this._scan0ID),
                this._sound.play("scan1"))));
      }));
  }
  onDestroy() {
    this._sound.stop();
  }
}
export { AudioController };
