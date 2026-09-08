import * as nt from "react";
import { MathUtils } from "./../engine/index.js";
import { events } from "./../state/events.js";
import { resourceConfig } from "./../config/resources.js";
function Preloader() {
  const preloaderRef = nt.useRef(null),
    [progress, setProgress] = nt.useState(0);
  return (
    nt.useEffect(() => {
      let s = 0,
        h = !1;
      const l = setInterval(() => {
          ((s = MathUtils.damp(s, events.loading, 0.016, 1)),
            s >= 0.99 && (s = 1),
            setProgress(s),
            h &&
              s >= 1 &&
              ((h = !1),
              (preloaderRef.current.style.transition = "opacity 600ms cubic-bezier(0,0,.58,1)"),
              (preloaderRef.current.style.opacity = "0"),
              setTimeout(() => {
                ((preloaderRef.current.style.display = "none"), events.emit(events.PLAY_BGM));
              }, 600)));
        }),
        g = () => {
          h = !0;
        };
      return (
        events.reset(),
        events.on(events.PRELOADED, g),
        () => {
          (clearInterval(l), events.clear());
        }
      );
    }, []),
    (
      <aside id="preloader" ref={preloaderRef}>
        <div className="progress-bar">
          <svg className="progress-bar-svg" viewBox="0 0 1709.0400390625 323.0625" fill="none">
            <path
              className="speed-line"
              id="process"
              d="M2.30809 318.07Q21.0208 316.441 50.1395 311.552Q108.449 301.761 160.401 285.447Q187.503 276.937 211.151 264.212Q225.389 256.551 250.01 240.238Q275.87 223.104 291.318 214.863Q317.146 201.086 347.378 191.695Q407.665 172.97 460.721 167.081Q495.936 163.173 558.47 163.173Q585.817 163.173 628.557 141.714Q654.353 128.763 708.923 94.4123Q742.671 73.1683 758.993 63.6874Q786.229 47.8662 806.111 39.6039Q862.305 16.252 914.714 7.87042Q961.797 0.340553 1040.78 0.0125411Q1117.18 -0.304734 1171.71 7.40653Q1227.48 15.2934 1289.78 35.6259Q1321.15 45.8667 1370.62 65.0861Q1407.99 79.6092 1425.84 85.4202Q1454.72 94.8298 1481 99.0339Q1520.17 105.3 1617.15 102.785Q1665.69 101.526 1706.36 99.0087C1706.42 99.0046 1706.48 99.0025 1706.54 99.0025C1707.92 99.0025 1709.04 100.122 1709.04 101.503C1709.04 102.838 1707.99 103.928 1706.68 103.999Q1665.91 106.522 1617.28 107.783Q1519.84 110.31 1480.22 103.971Q1453.55 99.7051 1424.29 90.1744Q1406.31 84.3207 1368.81 69.7466Q1319.47 50.5771 1288.22 40.3791Q1226.35 20.1827 1171.01 12.3573Q1116.83 4.69672 1040.8 5.0125Q962.205 5.3389 915.504 12.8077Q863.678 21.0959 808.029 44.2211Q788.454 52.356 761.504 68.0109Q745.26 77.4469 711.586 98.6438Q656.812 133.123 630.801 146.182Q587.002 168.173 558.47 168.173Q496.212 168.173 461.273 172.051Q408.69 177.886 348.862 196.47Q319.081 205.72 293.672 219.274Q278.433 227.403 252.771 244.406Q227.96 260.845 213.52 268.615Q189.453 281.565 161.899 290.218Q109.617 306.635 50.9674 316.483Q21.6568 321.404 2.74708 323.05C2.6658 323.058 2.58338 323.063 2.5 323.063C1.11929 323.063 0 321.943 0 320.563C0 319.246 1.01704 318.168 2.30809 318.07Z"
            />
            <defs>
              <linearGradient
                xmlns="http://www.w3.org/2000/svg"
                id="linear_0"
                x1="0.14628095304966532%"
                y1="50%"
                x2="99.85371904695035%"
                y2="50%"
                gradientUnits="objectBoundingBox"
              >
                <stop offset="0" stopColor="#000000" stopOpacity="0" />
                <stop offset={0.2341 * progress} stopColor="#FFFFFF" stopOpacity="0.44" />
                <stop offset={0.5278 * progress} stopColor="#FFFFFF" stopOpacity="1" />
                <stop offset={0.7698 * progress} stopColor="#FFFFFF" stopOpacity="0.49" />
                <stop offset={1 * progress} stopColor="#000000" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>
        <div className="progress-num">
          <p>
            {Math.floor(progress * 100)}
            {"%"}
          </p>
        </div>
        <div className="version">{resourceConfig.VERSION}</div>
      </aside>
    )
  );
}
export { Preloader };
