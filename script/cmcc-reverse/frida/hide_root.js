import Java from "frida-java-bridge";
'use strict';

function isBadPath(p) {
  if (!p) return false;
  return /(^|\/)(su|su\.bak|magisk|magiskhide|superuser|daemonsu|busybox|frida-server|frida-agent|frida|gum-js-loop|gmain|xposed|edxposed|lsposed)(\/|$)/i.test(p)
      || /\/su(\/|$)/i.test(p)
      || /magisk|superuser|daemonsu|frida|xposed/i.test(p);
}

Java.perform(function () {
  console.log('[hide] java hooks start');

  try {
    var File = Java.use('java.io.File');
    var exists = File.exists;
    File.exists.implementation = function () {
      var p = this.getAbsolutePath();
      if (isBadPath(p)) { console.log('[hide] File.exists ' + p); return false; }
      return exists.call(this);
    };
    var isFile = File.isFile;
    File.isFile.implementation = function () {
      var p = this.getAbsolutePath();
      if (isBadPath(p)) return false;
      return isFile.call(this);
    };
    var canExecute = File.canExecute;
    File.canExecute.implementation = function () {
      var p = this.getAbsolutePath();
      if (isBadPath(p)) return false;
      return canExecute.call(this);
    };
  } catch (e) { console.log('[hide] File hook error ' + e); }

  try {
    var Runtime = Java.use('java.lang.Runtime');
    function fakeProcess() { return Runtime.getRuntime().exec('/system/bin/echo'); }
    var execStr = Runtime.exec.overload('java.lang.String');
    execStr.implementation = function (cmd) {
      if (isBadPath(cmd) || /which\s+su|\bsu\b|magisk|frida|xposed/i.test(cmd)) {
        console.log('[hide] Runtime.exec ' + cmd); return fakeProcess();
      }
      return execStr.call(this, cmd);
    };
    var execArr = Runtime.exec.overload('[Ljava.lang.String;');
    execArr.implementation = function (arr) {
      var cmd = arr ? arr.join(' ') : '';
      if (isBadPath(cmd) || /which\s+su|\bsu\b|magisk|frida|xposed/i.test(cmd)) {
        console.log('[hide] Runtime.exec[] ' + cmd); return fakeProcess();
      }
      return execArr.call(this, arr);
    };
    var exit = Runtime.exit.overload('int');
    exit.implementation = function (code) { console.log('[hide] Runtime.exit ' + code); };
    var halt = Runtime.halt.overload('int');
    halt.implementation = function (code) { console.log('[hide] Runtime.halt ' + code); };
  } catch (e) { console.log('[hide] Runtime hook error ' + e); }

  try {
    var PB = Java.use('java.lang.ProcessBuilder');
    var start = PB.start.overload();
    start.implementation = function () {
      var cmd = this.command().join(' ');
      if (isBadPath(cmd) || /which\s+su|\bsu\b|magisk|frida|xposed/i.test(cmd)) {
        console.log('[hide] ProcessBuilder ' + cmd);
        return Java.use('java.lang.Runtime').getRuntime().exec('/system/bin/echo');
      }
      return start.call(this);
    };
  } catch (e) { console.log('[hide] ProcessBuilder hook error ' + e); }

  try {
    var Build = Java.use('android.os.Build');
    Build.TAGS.value = 'release-keys';
    Build.TYPE.value = 'user';
    Build.FINGERPRINT.value = 'Xiaomi/23127PN0CC/23127PN0CC:12/SKQ1.220303.001/V14.0.6.0.TMCCNXM:user/release-keys';
    Build.MODEL.value = '23127PN0CC';
    Build.MANUFACTURER.value = 'Xiaomi';
    Build.BRAND.value = 'Xiaomi';
    Build.DEVICE.value = '23127PN0CC';
    Build.PRODUCT.value = '23127PN0CC';
    Build.HARDWARE.value = 'qcom';
    Build.BOARD.value = 'kalama';
  } catch (e) { console.log('[hide] Build hook error ' + e); }

  try {
    var SP = Java.use('android.os.SystemProperties');
    var get1 = SP.get.overload('java.lang.String');
    get1.implementation = function (k) {
      if (k === 'ro.debuggable') return '0';
      if (k === 'ro.secure') return '1';
      if (k === 'ro.build.tags') return 'release-keys';
      if (k === 'ro.build.type') return 'user';
      if (k === 'ro.kernel.qemu') return '0';
      if (k === 'ro.hardware') return 'qcom';
      if (k === 'ro.product.model') return '23127PN0CC';
      if (k === 'ro.product.manufacturer') return 'Xiaomi';
      if (k === 'ro.product.brand') return 'Xiaomi';
      if (k === 'ro.product.name') return '23127PN0CC';
      if (k === 'ro.product.device') return '23127PN0CC';
      if (k === 'ro.product.board') return 'kalama';
      return get1.call(this, k);
    };
    var get2 = SP.get.overload('java.lang.String', 'java.lang.String');
    get2.implementation = function (k, def) { return get1.call(this, k) || def; };
  } catch (e) { console.log('[hide] SystemProperties hook error ' + e); }

  try {
    var System = Java.use('java.lang.System');
    var sysExit = System.exit.overload('int');
    sysExit.implementation = function (code) { console.log('[hide] System.exit ' + code); };
  } catch (e) { console.log('[hide] System.exit hook error ' + e); }

  try {
    var Dialog = Java.use('android.app.Dialog');
    var show = Dialog.show.overload();
    show.implementation = function () {
      var name = this.getClass().getName();
      if (name.indexOf('DECMsgDialog') >= 0 || /MsgDialog|Risk|Security/i.test(name)) {
        console.log('[hide] blocked dialog ' + name);
        return;
      }
      return show.call(this);
    };
  } catch (e) { console.log('[hide] Dialog hook error ' + e); }

  console.log('[hide] java hooks done');
});

// native file access hooks
function findExport(name) {
  try { if (typeof Module.findGlobalExportByName === 'function') return Module.findGlobalExportByName(name); } catch (e) {}
  try { if (typeof Module.getExportByName === 'function') return Module.getExportByName(null, name); } catch (e) {}
  try { if (typeof Module.findExportByName === 'function') return Module.findExportByName(null, name); } catch (e) {}
  return null;
}
function hookPath(name, argIndex) {
  var p = findExport(name);
  if (!p) return;
  try {
    Interceptor.attach(p, {
      onEnter: function (args) {
        try {
          var path = args[argIndex].readCString();
          this.hide = isBadPath(path);
          if (this.hide) console.log('[hide] ' + name + ' ' + path);
        } catch (e) { this.hide = false; }
      },
      onLeave: function (retval) {
        if (this.hide) retval.replace(ptr('-1'));
      }
    });
  } catch (e) { console.log('[hide] native hook error ' + name + ' ' + e); }
}
hookPath('open', 0);
hookPath('openat', 1);
hookPath('access', 0);
hookPath('stat', 0);
hookPath('lstat', 0);
hookPath('__lxstat', 0);
hookPath('stat64', 0);
hookPath('lstat64', 0);
console.log('[hide] native hooks done');
