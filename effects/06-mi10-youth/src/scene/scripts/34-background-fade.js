/* Scene behavior: background-fade. Registered in original execution order. */
var BackgroundFade = pc.createScript("backgroundFade");
BackgroundFade.prototype.initialize = function () {
  this.div = document.createElement("div");
  this.div.style.backgroundColor = "rgba(0,0,0,1)";
  this.div.style.width = "100%";
  this.div.style.height = "100%";
  this.div.style.position = "fixed";
  this.div.style.display = "block";
  document.body.appendChild(this.div);
  this.colorTimeCount = 0;
  this.isCanFade = false;
  this.app.on("background_fade", this.BGFade, this);
};
BackgroundFade.prototype.update = function (i) {
  if (0 === this.currentPhoneState) {
    if (this.isCanFade)
      if (this.colorTimeCount < 1) {
        this.colorTimeCount += i;
        var t;
        t = 1 - pc.math.clamp(this.colorTimeCount, 0, 1);
        this.div.style.backgroundColor = "rgba(0,0,0," + t + ")";
      } else {
        this.div.style.display = "none";
        this.isCanFade = false;
      }
  } else if (this.isCanFade)
    if (this.colorTimeCount < 2.5) {
      this.colorTimeCount += 6 * i;
      var o = 0;
      this.colorTimeCount < 1 && (o = pc.math.clamp(this.colorTimeCount, 0, 1));
      this.colorTimeCount >= 1 && this.colorTimeCount < 1.5 && (o = 1);
      this.colorTimeCount >= 1.5 &&
        this.colorTimeCount < 2.5 &&
        (o = 1 - pc.math.clamp(this.colorTimeCount - 1.5, 0, 1));
      this.div.style.backgroundColor = "rgba(0,0,0," + o + ")";
    } else {
      this.div.style.display = "none";
      this.isCanFade = false;
    }
};
BackgroundFade.prototype.BGFade = function (i) {
  this.isCanFade = true;
  this.div.style.display = "block";
  this.colorTimeCount = 0;
  this.currentPhoneState = i;
};
