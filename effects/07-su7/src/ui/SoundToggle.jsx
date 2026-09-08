import * as nt from "react";
import { events } from "./../state/events.js";
import { resourceConfig } from "./../config/resources.js";
function SoundToggle() {
  const [muted, setMuted] = nt.useState(!1);
  return (
    <>
      {null}
      <div className="Mute-container">
        <div
          className="Mute-content"
          onClick={() => {
            (setMuted(!muted), events.emit(events.MUTE, !muted));
          }}
        >
          <img
            src={`${resourceConfig.autoURL(`res/icon/${muted ? "close.png" : "open.png"}`)}`}
            alt=""
          />
        </div>
      </div>
    </>
  );
}
export { SoundToggle };
