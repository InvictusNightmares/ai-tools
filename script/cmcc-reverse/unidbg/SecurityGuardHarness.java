package cmcc;

import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.arm.backend.Unicorn2Factory;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.*;
import com.github.unidbg.linux.android.dvm.array.ArrayObject;
import com.github.unidbg.linux.android.dvm.wrapper.DvmInteger;
import com.github.unidbg.linux.android.dvm.jni.ProxyDvmObject;
import java.util.HashMap;
import java.util.Map;
import com.github.unidbg.linux.android.dvm.jni.ProxyClassFactory;
import com.github.unidbg.memory.Memory;
import junit.framework.TestCase;

import java.io.File;

/*
 * SecurityGuard unidbg harness.
 *
 * Status: loads libsgmainso, executes JNI_OnLoad, calls 10101/10602/10401.
 * 10101 no longer crashes with the JNI stubs below, but 10602 still throws
 * SecException 106440105 because the runtime appKey/authCode/context are not
 * available in the standalone plugin. See README.md.
 *
 * Env:
 *   SG_APK  nested libsgmain.so (default: out/securityguard/libsgmain.so)
 *   SG_SO   libsgmainso-*.so  (default: out/securityguard/sgmain/lib/arm64-v8a/libsgmainso-5.6.230509.so)
 */
public class SecurityGuardHarness extends TestCase {
    private static class Jni extends AbstractJni {
        @Override
        public DvmObject<?> callObjectMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {
            System.out.println("[jni] object: " + signature);
            if (signature.startsWith("android/content/Context->getPackageName") ||
                signature.startsWith("android/app/Application->getPackageName") ||
                signature.startsWith("android/content/ContextWrapper->getPackageName")) {
                return new StringObject(vm, "com.greenpoint.android.mc10086.activity");
            }
            if (signature.startsWith("android/content/Context->getApplicationContext")) {
                return dvmObject;
            }
            if (signature.startsWith("java/lang/ClassLoader->loadClass") || signature.startsWith("java/lang/ClassLoader->findClass")) {
                try {
                    StringObject name = varArg.getObjectArg(0);
                    String cls = name.getValue().replace('.', '/');
                    System.out.println("[jni] ClassLoader.loadClass(" + cls + ")");
                    return vm.resolveClass(cls);
                } catch (Throwable t) {
                    System.out.println("[jni] ClassLoader.loadClass error: " + t);
                }
            }
            if (signature.startsWith("android/content/Context->getFilesDir") ||
                signature.startsWith("android/content/Context->getCacheDir") ||
                signature.startsWith("android/content/Context->getDir")) {
                return vm.resolveClass("java/io/File").newObject(new File("/tmp/sgfiles"));
            }
            return super.callObjectMethod(vm, dvmObject, signature, varArg);
        }

        @Override
        public DvmObject<?> callStaticObjectMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if (signature.startsWith("com/taobao/wireless/security/adapter/common/SPUtility2->readSS") ||
                signature.startsWith("com/taobao/wireless/security/adapter/common/SPUtility2->readFromSPUnified") ||
                signature.startsWith("com/taobao/wireless/security/adapter/common/SPUtility2->read(")) {
                System.out.println("[jni] stub SP read: " + signature);
                return null;
            }
            System.out.println("[jni] static object: " + signature);
            if (signature.contains("getMainPluginClassLoader") || signature.contains("getMainPluginParentClassLoader")) {
                System.out.println("[jni] return ClassLoader for " + signature);
                return vm.resolveClass("java/lang/ClassLoader").newObject(null);
            }
            return super.callStaticObjectMethod(vm, dvmClass, signature, varArg);
        }

        @Override
        public boolean callStaticBooleanMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if (signature.startsWith("com/taobao/wireless/security/adapter/common/SPUtility2->writeSS") ||
                signature.startsWith("com/taobao/wireless/security/adapter/common/SPUtility2->removeFromSPUnified")) {
                System.out.println("[jni] stub SP bool: " + signature);
                return true;
            }
            return super.callStaticBooleanMethod(vm, dvmClass, signature, varArg);
        }

        @Override
        public int callStaticIntMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if (signature.startsWith("com/taobao/wireless/security/adapter/common/SPUtility2->saveToFileUnifiedForNative")) {
                System.out.println("[jni] stub SP int: " + signature);
                return 0;
            }
            return super.callStaticIntMethod(vm, dvmClass, signature, varArg);
        }

        @Override
        public void callStaticVoidMethod(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            if (signature.startsWith("com/taobao/wireless/security/adapter/common/SPUtility2->write")) {
                System.out.println("[jni] stub SP void: " + signature);
                return;
            }
            super.callStaticVoidMethod(vm, dvmClass, signature, varArg);
        }

        @Override
        public int callIntMethod(BaseVM vm, DvmObject<?> dvmObject, String signature, VarArg varArg) {
            if (signature.startsWith("android/content/Context->checkSelfPermission") ||
                signature.startsWith("android/content/Context->checkCallingOrSelfPermission")) {
                System.out.println("[jni] stub permission: " + signature);
                return 0;
            }
            return super.callIntMethod(vm, dvmObject, signature, varArg);
        }

        @Override
        public DvmObject<?> newObject(BaseVM vm, DvmClass dvmClass, String signature, VarArg varArg) {
            System.out.println("[jni] newObject: " + signature);
            if (signature.contains("SecException-><init>")) {
                try {
                    System.out.println("[jni] SecException msg=" + varArg.getObjectArg(0) + " code=" + varArg.getIntArg(1));
                } catch (Throwable t) {
                    System.out.println("[jni] SecException arg read error: " + t);
                }
                return dvmClass.newObject(null);
            }
            return super.newObject(vm, dvmClass, signature, varArg);
        }
    }

    public static void main(String[] args) throws Exception {
        new SecurityGuardHarness().test();
    }

    public void test() throws Exception {
        AndroidEmulator emulator = AndroidEmulatorBuilder.for64Bit()
                .setProcessName("com.greenpoint.android.mc10086.activity")
                .addBackendFactory(new Unicorn2Factory(true))
                .build();
        try {
            Memory memory = emulator.getMemory();
            memory.setLibraryResolver(new AndroidResolver(23));

            File sgApk = new File(System.getenv().getOrDefault("SG_APK", "out/securityguard/libsgmain.so"));
            File sgSo = new File(System.getenv().getOrDefault("SG_SO",
                    "out/securityguard/sgmain/lib/arm64-v8a/libsgmainso-5.6.230509.so"));
            VM vm = emulator.createDalvikVM(sgApk);
            vm.setJni(new Jni());
            vm.setVerbose(true);

            System.out.println("[smoke] resolve JNICLibrary=" + vm.resolveClass("com/taobao/wireless/security/adapter/JNICLibrary"));
            System.out.println("[smoke] resolve SecurityGuardMainPlugin=" + vm.resolveClass("com/alibaba/wireless/security/mainplugin/SecurityGuardMainPlugin"));
            System.out.println("[smoke] resolve SecException=" + vm.resolveClass("com/alibaba/wireless/security/open/SecException"));
            DalvikModule dm = vm.loadLibrary(sgSo, true);
            System.out.println("[smoke] module=" + dm.getModule());
            dm.callJNI_OnLoad(emulator);
            DvmClass c = vm.resolveClass("com/taobao/wireless/security/adapter/JNICLibrary");
            System.out.println("[smoke] class=" + c);
            String sign = "doCommandNative(I[Ljava/lang/Object;)Ljava/lang/Object;";
            DvmObject<?> context = vm.resolveClass("android/content/Context").newObject(null);
            String[] appKeys = {"", "0F09868011039", "jtztty_sdk#GD70958956615", "zgydAppSDK", "default", "android"};
            String[] authCodes = {""};
            for (String appKey : appKeys) {
                for (String authCode : authCodes) {
                    try {
                        ArrayObject initArgs = new ArrayObject(
                                context,
                                new StringObject(vm, "0F09868011039"),
                                new StringObject(vm, appKey),
                                new StringObject(vm, authCode),
                                new StringObject(vm, "com.greenpoint.android.mc10086.activity"),
                                new StringObject(vm, "12.5.6"),
                                new StringObject(vm, "12"),
                                new StringObject(vm, "com.greenpoint.android.mc10086.activity"));
                        DvmObject<?> ret = c.callStaticJniMethodObject(emulator, sign, 10101, initArgs);
                        System.out.println("[smoke] init appKey='" + appKey + "' auth='" + authCode + "' ret=" + (ret == null ? null : ret.getValue()));
                    } catch (Throwable t) {
                        System.out.println("[smoke] init appKey='" + appKey + "' auth='" + authCode + "' error=" + t);
                    }
                    for (int idx = 0; idx <= 2; idx++) {
                        try {
                            ArrayObject keyArgs = new ArrayObject(DvmInteger.valueOf(vm, idx), new StringObject(vm, authCode));
                            DvmObject<?> ret = c.callStaticJniMethodObject(emulator, sign, 10602, keyArgs);
                            if (ret != null) System.out.println("[smoke] getAppKey idx=" + idx + " appKey='" + appKey + "' ret=" + ret.getValue());
                        } catch (Throwable t) {
                            System.out.println("[smoke] getAppKey idx=" + idx + " error=" + t);
                        }
                    }
                    for (int type = 0; type <= 1; type++) {
                        try {
                            Map<String, String> params = new HashMap<>();
                            if (type == 0) params.put("SEEDKEY", "1234567890"); else params.put("INPUT", "test");
                            ArrayObject signArgs = new ArrayObject(
                                    ProxyDvmObject.createObject(vm, params),
                                    new StringObject(vm, appKey),
                                    DvmInteger.valueOf(vm, type),
                                    new StringObject(vm, authCode));
                            DvmObject<?> ret = c.callStaticJniMethodObject(emulator, sign, 10401, signArgs);
                            if (ret != null) System.out.println("[smoke] sign type=" + type + " appKey='" + appKey + "' ret=" + ret.getValue());
                        } catch (Throwable t) {
                            System.out.println("[smoke] sign type=" + type + " error=" + t);
                        }
                    }
                }
            }
        } finally {
            emulator.close();
        }
    }
}
