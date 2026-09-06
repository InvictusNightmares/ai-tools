/* UI behavior: video-player. Plain source, shared classic-script scope. */
function vidx() {
  var _value28 = 0;
  var _value29 = document.getElementsByClassName("video_mp4");
  for (var _value30 = 0; _value30 < _value29.length; _value30++) {
    vid_width = _value29[_value30].offsetWidth;
    _value28 = vid_width * 0.5625 + "px";
    _value29[_value30].style.height = _value28;
  }
  var _value31 = document.getElementsByClassName("hotimages");
  for (var _value30 = 0; _value30 < _value31.length; _value30++) {
    _value31[_value30].style.width = vid_width + "px";
    _value31[_value30].style.height = _value28;
    _value31[_value30].style.backgroundSize = vid_width + "px" + " " + _value28;
  }
  document.getElementById("image_end1").style.height = _value28;
  document.getElementById("image_end2").style.height = _value28;
  position1 = "-" + vid_width + "px" + " " + "0px";
  position2 = "0px" + " " + "0px";
  position3 = vid_width + "px" + " " + "0px";
  positionB1 = "-" + vid_width + "px" + " " + "0px";
  positionB2 = "0px" + " " + "0px";
  positionB3 = vid_width + "px" + " " + "0px";
  switch (imgid) {
    case 1:
      image_1x.style.backgroundImage = "url('./Img/images/A5.jpg')";
      image_2x.style.backgroundImage = "url('./Img/images/A1.jpg')";
      image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
      image_1x.style.backgroundPosition = position1;
      image_2x.style.backgroundPosition = position2;
      image_3x.style.backgroundPosition = position3;
      break;
    case 2:
      image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
      image_2x.style.backgroundImage = "url('./Img/images/A1.jpg')";
      image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
      image_1x.style.backgroundPosition = position3;
      image_2x.style.backgroundPosition = position1;
      image_3x.style.backgroundPosition = position2;
      break;
    case 3:
      image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
      image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
      image_3x.style.backgroundImage = "url('./Img/images/A2.jpg')";
      image_1x.style.backgroundPosition = position2;
      image_2x.style.backgroundPosition = position3;
      image_3x.style.backgroundPosition = position1;
      break;
    case 4:
      image_1x.style.backgroundImage = "url('./Img/images/A3.jpg')";
      image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
      image_3x.style.backgroundImage = "url('./Img/images/A5.jpg')";
      image_1x.style.backgroundPosition = position1;
      image_2x.style.backgroundPosition = position2;
      image_3x.style.backgroundPosition = position3;
      break;
    case 5:
      image_1x.style.backgroundImage = "url('./Img/images/A1.jpg')";
      image_2x.style.backgroundImage = "url('./Img/images/A4.jpg')";
      image_3x.style.backgroundImage = "url('./Img/images/A5.jpg')";
      image_1x.style.backgroundPosition = position3;
      image_2x.style.backgroundPosition = position1;
      image_3x.style.backgroundPosition = position2;
      break;
  }
  switch (imgidB) {
    case 1:
      imageB_1x.style.backgroundImage = "url('./Img/images/B5.jpg')";
      imageB_2x.style.backgroundImage = "url('./Img/images/B1.jpg')";
      imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
      imageB_1x.style.backgroundPosition = positionB1;
      imageB_2x.style.backgroundPosition = positionB2;
      imageB_3x.style.backgroundPosition = positionB3;
      break;
    case 2:
      imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
      imageB_2x.style.backgroundImage = "url('./Img/images/B1.jpg')";
      imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
      imageB_1x.style.backgroundPosition = positionB3;
      imageB_2x.style.backgroundPosition = positionB1;
      imageB_3x.style.backgroundPosition = positionB2;
      break;
    case 3:
      imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
      imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
      imageB_3x.style.backgroundImage = "url('./Img/images/B2.jpg')";
      imageB_1x.style.backgroundPosition = positionB2;
      imageB_2x.style.backgroundPosition = positionB3;
      imageB_3x.style.backgroundPosition = positionB1;
      break;
    case 4:
      imageB_1x.style.backgroundImage = "url('./Img/images/B3.jpg')";
      imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
      imageB_3x.style.backgroundImage = "url('./Img/images/B5.jpg')";
      imageB_1x.style.backgroundPosition = positionB1;
      imageB_2x.style.backgroundPosition = positionB2;
      imageB_3x.style.backgroundPosition = positionB3;
      break;
    case 5:
      imageB_1x.style.backgroundImage = "url('./Img/images/B1.jpg')";
      imageB_2x.style.backgroundImage = "url('./Img/images/B4.jpg')";
      imageB_3x.style.backgroundImage = "url('./Img/images/B5.jpg')";
      imageB_1x.style.backgroundPosition = positionB3;
      imageB_2x.style.backgroundPosition = positionB1;
      imageB_3x.style.backgroundPosition = positionB2;
      break;
  }
}
vidx();
function stopall() {
  if (vid1 == 1) {
    videoend(1);
  }
  if (vid2 == 1) {
    videoend(2);
  }
  if (vid3 == 1) {
    videoend(3);
  }
  if (vid4 == 1) {
    videoend(4);
  }
  if (vid5 == 1) {
    videoend(5);
  }
}
var playing = 0;
document.getElementById("play_1").onclick = function () {
  if (playing == 1) {
  } else {
    stopall();
  }
  playing = 1;
  document.getElementById("video_1").play();
  document.getElementById("play_1").style.opacity = "0";
  setTimeout(function () {
    document.getElementById("play_1").style.display = "none";
    document.getElementById("video_1").style = "cursor:pointer";
  }, 250);
};
document.getElementById("video_1").onclick = function () {
  document.getElementById("video_1").style = "";
  document.getElementById("video_1").pause();
  document.getElementById("play_1").style.display = "block";
  setTimeout(function () {
    document.getElementById("play_1").style.opacity = "1";
  }, 50);
};
document.getElementById("play_2").onclick = function () {
  if (playing == 2) {
  } else {
    stopall();
  }
  playing = 2;
  document.getElementById("video_2").play();
  document.getElementById("play_2").style.opacity = "0";
  setTimeout(function () {
    document.getElementById("play_2").style.display = "none";
    document.getElementById("video_2").style = "cursor:pointer";
  }, 250);
};
document.getElementById("video_2").onclick = function () {
  document.getElementById("video_2").style = "";
  document.getElementById("video_2").pause();
  document.getElementById("play_2").style.display = "block";
  setTimeout(function () {
    document.getElementById("play_2").style.opacity = "1";
  }, 50);
};
document.getElementById("play_3").onclick = function () {
  if (playing == 3) {
  } else {
    stopall();
  }
  playing = 3;
  document.getElementById("video_3").play();
  document.getElementById("play_3").style.opacity = "0";
  setTimeout(function () {
    document.getElementById("play_3").style.display = "none";
    document.getElementById("video_3").style = "cursor:pointer";
  }, 250);
};
document.getElementById("video_3").onclick = function () {
  document.getElementById("video_3").style = "";
  document.getElementById("video_3").pause();
  document.getElementById("play_3").style.display = "block";
  setTimeout(function () {
    document.getElementById("play_3").style.opacity = "1";
  }, 50);
};
document.getElementById("play_4").onclick = function () {
  if (playing == 4) {
  } else {
    stopall();
  }
  playing = 4;
  document.getElementById("video_4").play();
  document.getElementById("play_4").style.opacity = "0";
  setTimeout(function () {
    document.getElementById("play_4").style.display = "none";
    document.getElementById("video_4").style = "cursor:pointer";
  }, 250);
};
document.getElementById("video_4").onclick = function () {
  document.getElementById("video_4").style = "";
  document.getElementById("video_4").pause();
  document.getElementById("play_4").style.display = "block";
  setTimeout(function () {
    document.getElementById("play_4").style.opacity = "1";
  }, 50);
};
document.getElementById("play_5").onclick = function () {
  if (playing == 5) {
  } else {
    stopall();
  }
  playing = 5;
  document.getElementById("video_5").play();
  document.getElementById("play_5").style.opacity = "0";
  setTimeout(function () {
    document.getElementById("play_5").style.display = "none";
    document.getElementById("video_5").style = "cursor:pointer";
  }, 250);
};
document.getElementById("video_5").onclick = function () {
  document.getElementById("video_5").style = "";
  document.getElementById("video_5").pause();
  document.getElementById("play_5").style.display = "block";
  setTimeout(function () {
    document.getElementById("play_5").style.opacity = "1";
  }, 50);
};
function videoend(_videoIndex) {
  switch (_videoIndex) {
    case 1:
      vid1 = 0;
      document.getElementById("play_1").style.display = "block";
      document.getElementById("video_1").load();
      document.getElementById("play_1").style.opacity = "1";
      break;
    case 2:
      vid2 = 0;
      document.getElementById("play_2").style.display = "block";
      document.getElementById("video_2").load();
      document.getElementById("play_2").style.opacity = "1";
      break;
    case 3:
      vid3 = 0;
      document.getElementById("play_3").style.display = "block";
      document.getElementById("video_3").load();
      document.getElementById("play_3").style.opacity = "1";
      break;
    case 4:
      vid4 = 0;
      document.getElementById("play_4").style.display = "block";
      document.getElementById("video_4").load();
      document.getElementById("play_4").style.opacity = "1";
      break;
    case 5:
      vid5 = 0;
      document.getElementById("play_5").style.display = "block";
      document.getElementById("video_5").load();
      document.getElementById("play_5").style.opacity = "1";
      break;
  }
}
var vid1 = 0;
var vid2 = 0;
var vid3 = 0;
var vid4 = 0;
var vid5 = 0;
function playinend(_videoIndex2) {
  switch (_videoIndex2) {
    case 1:
      vid1 = 1;
      break;
    case 2:
      vid2 = 1;
      break;
    case 3:
      vid3 = 1;
      break;
    case 4:
      vid4 = 1;
      break;
    case 5:
      vid5 = 1;
      break;
  }
}
