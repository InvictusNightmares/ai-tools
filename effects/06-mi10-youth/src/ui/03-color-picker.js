/* UI behavior: color-picker. Plain source, shared classic-script scope. */
function funcB(_colorIndex) {
  bx = _colorIndex;
  document.getElementById("btnB_img_01").src = "Img/Icon_sc/color1_1.png";
  document.getElementById("btnB_img_02").src = "Img/Icon_sc/color2_1.png";
  document.getElementById("btnB_img_03").src = "Img/Icon_sc/color3_1.png";
  document.getElementById("btnB_img_04").src = "Img/Icon_sc/color4_1.png";
  document.getElementById("btnB_img_05").src = "Img/Icon_sc/color5_1.png";
  document.getElementById("btnB_01").style.opacity = "";
  document.getElementById("btnB_02").style.opacity = "";
  document.getElementById("btnB_03").style.opacity = "";
  document.getElementById("btnB_04").style.opacity = "";
  document.getElementById("btnB_05").style.opacity = "";
  switch (_colorIndex) {
    case 1:
      document.getElementById("btnB_img_01").src = "Img/Icon_sc/color1_2.png";
      document.getElementById("btnB_01").style.opacity = "1";
      try {
        iframe.contentWindow.app.fire("exterior:change_color", 0);
      } catch (_value0) {}
      break;
    case 2:
      document.getElementById("btnB_img_02").src = "Img/Icon_sc/color2_2.png";
      document.getElementById("btnB_02").style.opacity = "1";
      try {
        iframe.contentWindow.app.fire("exterior:change_color", 1);
      } catch (_value1) {}
      break;
    case 3:
      document.getElementById("btnB_img_03").src = "Img/Icon_sc/color3_2.png";
      document.getElementById("btnB_03").style.opacity = "1";
      try {
        iframe.contentWindow.app.fire("exterior:change_color", 2);
      } catch (_value10) {}
      break;
    case 4:
      document.getElementById("btnB_img_04").src = "Img/Icon_sc/color4_2.png";
      document.getElementById("btnB_04").style.opacity = "1";
      try {
        iframe.contentWindow.app.fire("exterior:change_color", 3);
      } catch (_value11) {}
      break;
    case 5:
      document.getElementById("btnB_img_05").src = "Img/Icon_sc/color5_2.png";
      document.getElementById("btnB_05").style.opacity = "1";
      try {
        iframe.contentWindow.app.fire("exterior:change_color", 4);
      } catch (_value12) {}
      break;
  }
}
funcB(4);
document.getElementById("btnB_01").onmouseover = function () {
  mouseOverB1();
};
document.getElementById("btnB_01").onmouseout = function () {
  mouseOutB1();
};
document.getElementById("btnB_01").onclick = function () {
  funcB(1);
};
function mouseOverB1() {
  document.getElementById("btnB_img_01").src = "Img/Icon_sc/color1_2.png";
}
function mouseOutB1() {
  if (bx != 1) {
    document.getElementById("btnB_img_01").src = "Img/Icon_sc/color1_1.png";
  }
}
document.getElementById("btnB_02").onmouseover = function () {
  mouseOverB2();
};
document.getElementById("btnB_02").onmouseout = function () {
  mouseOutB2();
};
document.getElementById("btnB_02").onclick = function () {
  funcB(2);
};
function mouseOverB2() {
  document.getElementById("btnB_img_02").src = "Img/Icon_sc/color2_2.png";
}
function mouseOutB2() {
  if (bx != 2) {
    document.getElementById("btnB_img_02").src = "Img/Icon_sc/color2_1.png";
  }
}
document.getElementById("btnB_03").onmouseover = function () {
  mouseOverB3();
};
document.getElementById("btnB_03").onmouseout = function () {
  mouseOutB3();
};
document.getElementById("btnB_03").onclick = function () {
  funcB(3);
};
function mouseOverB3() {
  document.getElementById("btnB_img_03").src = "Img/Icon_sc/color3_2.png";
}
function mouseOutB3() {
  if (bx != 3) {
    document.getElementById("btnB_img_03").src = "Img/Icon_sc/color3_1.png";
  }
}
document.getElementById("btnB_04").onmouseover = function () {
  mouseOverB4();
};
document.getElementById("btnB_04").onmouseout = function () {
  mouseOutB4();
};
document.getElementById("btnB_04").onclick = function () {
  funcB(4);
};
function mouseOverB4() {
  document.getElementById("btnB_img_04").src = "Img/Icon_sc/color4_2.png";
}
function mouseOutB4() {
  if (bx != 4) {
    document.getElementById("btnB_img_04").src = "Img/Icon_sc/color4_1.png";
  }
}
document.getElementById("btnB_05").onmouseover = function () {
  mouseOverB5();
};
document.getElementById("btnB_05").onmouseout = function () {
  mouseOutB5();
};
document.getElementById("btnB_05").onclick = function () {
  funcB(5);
};
function mouseOverB5() {
  document.getElementById("btnB_img_05").src = "Img/Icon_sc/color5_2.png";
}
function mouseOutB5() {
  if (bx != 5) {
    document.getElementById("btnB_img_05").src = "Img/Icon_sc/color5_1.png";
  }
}
