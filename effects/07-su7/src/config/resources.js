import { defineField as B } from "./../engine/fields.js";
import { Color, Vector2, Vector3 } from "./../engine/index.js";
import { events } from "./../state/events.js";
import { resolveAssetURL } from "./asset-url.js";
class ResourceConfig {
  constructor() {
    B(this, "RES_VERSION", "1.0.5");
    B(this, "CODE_VERSION", "1.1.4");
    B(this, "DEBUG", false);
    B(this, "COMPRESS", !0);
  }
  get VERSION() {
    return `res ${this.RES_VERSION} code ${this.CODE_VERSION}`;
  }
  autoURL(n) {
    const url = this.COMPRESS
      ? (n.includes(".raw") ||
          (n = n
            .replace(".jpg", ".webp")
            .replace(".jpeg", ".webp")
            .replace(".png", ".webp")
            .replace(".glb", ".bin")),
        n.replace("res/", `./${this.RES_VERSION}/`))
      : n;
    return resolveAssetURL(url);
  }
}
const resourceConfig = new ResourceConfig();
class SceneResources {
  constructor() {
    B(this, "maxSpeed", 20);
    B(this, "speedUpDuration", 2);
    B(this, "LAYER_CAPTURE", 31);
    B(this, "LAYER_PLANE_REFLECT", 29);
    B(this, "lightUpTime", 2);
    B(this, "sm_car");
    B(this, "sm_size");
    B(this, "sm_startroom");
    B(this, "sm_speedup");
    B(this, "sm_curvature");
    B(this, "sm_windspeed");
    B(this, "sm_linecar");
    B(this, "sm_carradar");
    B(this, "sm_simpleCar");
    B(this, "sm_car_lightbar");
    B(this, "ut_car_body_ao", {
      value: null,
    });
    B(this, "ut_startroom_ao", {
      value: null,
    });
    B(this, "ut_startroom_light", {
      value: null,
    });
    B(this, "ut_floor_normal", {
      value: null,
    });
    B(this, "ut_floor_roughness", {
      value: null,
    });
    B(this, "ut_cubeCapture", {
      value: null,
    });
    B(this, "ut_blurCapture", {
      value: null,
    });
    B(this, "ut_saLine", {
      value: null,
    });
    B(this, "ut_street", {
      value: null,
    });
    B(this, "ut_scar_matcap", {
      value: null,
    });
    B(this, "ut_white", {
      value: null,
    });
    B(this, "ut_dark", {
      value: null,
    });
    B(this, "ut_floorMap", {
      value: null,
    });
    B(this, "ut_car_body_t_gm", {
      value: null,
    });
    B(this, "ut_car_body_t_gm2", {
      value: null,
    });
    B(this, "ut_gm02_car_window_bc", {
      value: null,
    });
    B(this, "ut_gm02_car_window_roughness", {
      value: null,
    });
    B(this, "ut_gm02_floor_bc", {
      value: null,
    });
    B(this, "ut_police_Car_body_BC", {
      value: null,
    });
    B(this, "ut_police_floor_bc", {
      value: null,
    });
    B(this, "ut_env_night", {
      value: null,
    });
    B(this, "ut_env_light", {
      value: null,
    });
    B(this, "u_time", {
      value: 0,
    });
    B(this, "u_car_envMapIntensity", {
      value: 1,
    });
    B(this, "u_floor_typeSwitch", {
      value: 0,
    });
    B(this, "u_speedUpBackgroundValue", {
      value: 0,
    });
    B(this, "u_car_discard", {
      value: 1,
    });
    B(this, "u_speedTime", {
      value: 0,
    });
    B(this, "u_floorLightMapIntensity", {
      value: 0,
    });
    B(this, "u_floorLightMapColor", {
      value: new Color("#000000"),
    });
    B(this, "u_floorReflectIntensity", {
      value: 0,
    });
    B(this, "u_floorUVOffset", {
      value: new Vector2(),
    });
    B(this, "u_simpleCarCenter1", {
      value: new Vector3(),
    });
    B(this, "u_simpleCarCenter2", {
      value: new Vector3(),
    });
    B(this, "u_policeColorChange", {
      value: 0,
    });
    B(this, "u_reflect", {
      u_reflectTexture: {
        value: null,
      },
      u_reflectMatrix: {
        value: null,
      },
    });
    B(this, "u_m_car_window_orignData", {
      opacity: 0,
      roughness: 0,
      color: new Color(),
    });
    B(
      this,
      "colors",
      new Map([
        [
          "custom",
          {
            col: new Color("#ffc03f").convertSRGBToLinear(),
            hsl: {
              h: 40.31 / 360,
              s: 1,
              l: 0.6235,
            },
            bgUrl: "custom.png",
            rough: 0.03,
            metal: 0.1,
          },
        ],
        [
          "00",
          {
            col: new Color("#25d6e9").convertSRGBToLinear(),
            bgUrl: "b1.png",
            metal: 0.16,
          },
        ],
        [
          "01",
          {
            col: new Color("#7c8670").convertSRGBToLinear(),
            bgUrl: "b2.png",
            metal: 0.17,
          },
        ],
        [
          "02",
          {
            col: new Color("#9C9C9C").convertSRGBToLinear(),
            bgUrl: "b3.png",
            metal: 0.16,
          },
        ],
        [
          "03",
          {
            col: new Color("#D9D9D9").convertSRGBToLinear(),
            bgUrl: "b4.png",
          },
        ],
        [
          "04",
          {
            col: new Color("#7C6D83").convertSRGBToLinear(),
            bgUrl: "b5.png",
            rough: 0.03,
            metal: 0.27,
          },
        ],
        [
          "05",
          {
            col: new Color("#d15523").convertSRGBToLinear(),
            bgUrl: "b6.png",
            rough: 0.13,
          },
        ],
        [
          "06",
          {
            col: new Color("#7495be").convertSRGBToLinear(),
            bgUrl: "b7.png",
          },
        ],
        [
          "07",
          {
            col: new Color("#54657f").convertSRGBToLinear(),
            bgUrl: "b8.png",
            rough: 0.12,
            metal: 0.16,
          },
        ],
        [
          "08",
          {
            col: new Color("#2a2933").convertSRGBToLinear(),
            bgUrl: "b9.png",
            metal: 0.77,
          },
        ],
        [
          "09",
          {
            col: new Color("#FFFFFF").convertSRGBToLinear(),
            bgUrl: "b10.png",
            tcar: this.ut_car_body_t_gm,
          },
        ],
        [
          "10",
          {
            col: new Color("#FFFFFF").convertSRGBToLinear(),
            bgUrl: "b12.png",
            rough: 0.7,
            metal: 0,
            tcar: this.ut_car_body_t_gm2,
            tw: this.ut_gm02_car_window_bc,
            twr: this.ut_gm02_car_window_roughness,
            tf: this.ut_gm02_floor_bc,
          },
        ],
        [
          "11",
          {
            col: new Color("#FFFFFF").convertSRGBToLinear(),
            bgUrl: "b13.png",
            tcar: this.ut_police_Car_body_BC,
            tf: this.ut_police_floor_bc,
          },
        ],
      ]),
    );
    B(this, "u_carColor", {
      value: this.colors.get("00").col.clone(),
    });
    B(this, "u_carMetalness", {
      value: this.colors.get("00").metal,
    });
    B(this, "u_carRoughness", {
      value: 0,
    });
  }
  getCustomParams() {
    const r = new URLSearchParams(window.location.search).get("v");
    if (r && r.length == 10) {
      const s = r,
        h = parseInt(s.slice(6, 8), 16) / 255,
        l = parseInt(s.slice(8, 10), 16) / 255,
        g = s.slice(0, 6);
      if (
        (h && (this.colors.get("custom").rough = h), l && (this.colors.get("custom").metal = l), g)
      ) {
        const _ = new Color("#" + g);
        (this.colors.get("custom").col.copy(_),
          _.convertLinearToSRGB(),
          _.getHSL(this.colors.get("custom").hsl));
      }
      return "custom";
    }
    return r && r.includes("h") && r.length == 3 ? r.slice(1, 3) : 0;
  }
  generateCustomParams() {
    if (events.currentColorIndex == "custom") {
      let n = Math.round(this.colors.get("custom").rough * 255).toString(16);
      n.length < 2 && (n = "0" + n);
      let r = Math.round(this.colors.get("custom").metal * 255).toString(16);
      r.length < 2 && (r = "0" + r);
      const s = this.colors.get("custom").col.getHexString();
      return (
        (resourceConfig.DEBUG
          ? window.location.pathname + "?v="
          : window.location.pathname + "?v=") +
        s +
        n +
        r
      );
    } else
      return (
        (resourceConfig.DEBUG
          ? window.location.pathname + "?v=h"
          : window.location.pathname + "?v=h") + events.currentColorIndex
      );
  }
}
const resources = new SceneResources();
export { ResourceConfig, resourceConfig, SceneResources, resources };
