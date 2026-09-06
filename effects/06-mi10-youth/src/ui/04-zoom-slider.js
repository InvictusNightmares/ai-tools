/* UI behavior: zoom-slider. Plain source, shared classic-script scope. */
function creatslide() {
  for (var _value13 = 0.6; _value13 < 10;) {
    var _value14 = _value13.toFixed(1);
    var _value15 = document.createElement("div");
    _value15.className = "slides";
    _value15.id = "slides_" + _value14;
    if (
      _value14 == 0.6 ||
      _value14 == 1 ||
      _value14 == 2 ||
      _value14 == 3 ||
      _value14 == 4 ||
      _value14 == 5 ||
      _value14 == 6 ||
      _value14 == 7 ||
      _value14 == 8 ||
      _value14 == 9 ||
      _value14 == 10
    ) {
      _value15.className = "slides max";
    }
    if (_value14 == 0.6) {
      _value15.style.background = "#14a4ed";
    }
    var _slides_boxElement = document.getElementById("slides_box");
    _slides_boxElement.appendChild(_value15);
    _value13 += 0.1;
  }
}
creatslide();
var clientX2 = 0;
var moveact = 0;
var addxs = 30;
var elementx2 = document.getElementById("slidebtn_box");
elementx2.onmousemove = function () {
  mousemove2(event);
};
elementx2.onmousedown = function () {
  onmousedown2(event);
};
elementx2.onmouseup = function () {
  onmouseup2(event);
};
elementx2.onmouseleave = function () {
  onmouseup2(event);
};
elementx2.ontouchstart = ontouchstart2;
elementx2.ontouchmove = ontouchmove2;
elementx2.ontouchend = onmouseup2;
function onmousedown2(_event) {
  clientX_old = _event.clientX;
  moveact = 1;
}
function mousemove2(_event2) {
  clientX2 = _event2.clientX;
  mousetouchmove2();
}
function ontouchstart2(_event3) {
  clientX_old = _event3.touches[0].clientX;
  moveact = 1;
}
function ontouchmove2(_event4) {
  clientX2 = _event4.touches[0].clientX;
  mousetouchmove2();
}
function onmouseup2(_event5) {
  moveact = 0;
}
function mousetouchmove2() {
  if (moveact == 1 && addxs < 31 && addxs > -631) {
    var _value16 = clientX_old - clientX2;
    addxs -= _value16;
    if (addxs > 30) {
      addxs = 30;
    } else if (addxs < -630) {
      addxs = -630;
    }
    var _value17 = "translateX(" + addxs + "px)";
    var _value18 = "translateX(" + parseFloat(addxs + addxs * 0.1) + "px)";
    elementx2.style.transform = _value17;
    var _value19 = addxs / -70 + 1;
    addts = _value19.toFixed(1);
    var _value20 = document.getElementsByClassName("slides");
    for (i = 0; i < _value20.length; i++) {
      _value20[i].style = "";
    }
    var _value21 = "slides_" + addts;
    document.getElementById(_value21).style.background = "#14a4ed";
    var _value22 = 0;
    var _value23 = 0;
    if (addts < 5.1) {
      _value23 = parseFloat(addts).toFixed(5);
    } else if (addts < 6.1) {
      _value23 = ((parseFloat(addts) - 5) * 5 + 5).toFixed(5);
    } else if (addts < 7.1) {
      _value23 = ((parseFloat(addts) - 6) * 10 + 10).toFixed(5);
    } else if (addts < 8.1) {
      _value23 = ((parseFloat(addts) - 7) * 10 + 20).toFixed(5);
    } else if (addts < 9.1) {
      _value23 = ((parseFloat(addts) - 8) * 10 + 30).toFixed(5);
    } else if (addts < 10.1) {
      _value23 = ((parseFloat(addts) - 9) * 10 + 40).toFixed(5);
    }
    _value22 = parseFloat(_value23).toFixed(1);
    document.getElementById("sidetinfor").innerHTML = _value22 + "x";
    try {
      iframe.contentWindow.app.fire("phone:changeCameraScale", _value23);
    } catch (_value25) {}
    var _value24 = document.getElementsByClassName("slidetext");
    for (i = 0; i < _value24.length; i++) {
      _value24[i].style.color = "white";
    }
    if (addts == "0.6") {
      document.getElementById("slidet_0").style.color = "#14a4ed";
    }
    if (addts == "1.0") {
      document.getElementById("slidet_1").style.color = "#14a4ed";
    }
    if (addts == "5.0") {
      document.getElementById("slidet_2").style.color = "#14a4ed";
    }
    if (addts == "10.0") {
      document.getElementById("slidet_3").style.color = "#14a4ed";
    }
    clientX_old = clientX2;
  }
}
var vid = document.getElementById("img_box");
