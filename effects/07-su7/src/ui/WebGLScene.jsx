import * as nt from "react";
import { Viewer, aO, ACESFilmicToneMapping } from "./../engine/index.js";
import { events } from "./../state/events.js";
import { Experience } from "./../scene/experience.js";
function WebGLScene() {
  const canvasRef = nt.useRef(null);
  return (
    nt.useEffect(() => {
      const n = new Viewer({
        root: document.getElementById("root"),
        canvas: canvasRef.current,
        orientation: aO.LANDSCAPE,
        antialias: !1,
        toneMapping: ACESFilmicToneMapping,
        loader: {
          onProgress: (r, s, h) => (events.loading = Math.max(events.loading, s / h)),
          onLoad: () => (events.loading = 1),
        },
      });
      return (
        n.addNode(Experience),
        () => {
          n.destroy();
        }
      );
    }, []),
    (
      <aside className="webgl-wrapper">
        <canvas ref={canvasRef} className="webgl-canvas">
          {"No Canvas!"}
        </canvas>
        <div id="css-container" />
      </aside>
    )
  );
}
export { WebGLScene };
