import java.util.Properties

plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "app.tini.tini"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "app.tini.tini"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    // Release imzası android/key.properties'ten gelir (şablon: key.properties.example).
    // Dosya yoksa release derlemesi DURUR: debug anahtarıyla imzalı paket yanlışlıkla mağazaya
    // gitmesin. Yerel deneme APK'sı için açık kaçış: -PallowDebugSigning=true (uyarı basar).
    val signingProps = Properties().apply {
        val f = rootProject.file("key.properties")
        if (f.exists()) f.inputStream().use { load(it) }
    }
    val allowDebugSigning = project.findProperty("allowDebugSigning") == "true"
    val releaseRequested = gradle.startParameter.taskNames.any { it.contains("release", ignoreCase = true) }
    val requiredKeys = listOf("storeFile", "storePassword", "keyAlias", "keyPassword")

    if (releaseRequested && !allowDebugSigning) {
        if (signingProps.isEmpty) {
            throw GradleException(
                "Release imzası yok: android/key.properties oluştur (bkz. key.properties.example) " +
                    "ya da yerel deneme için -PallowDebugSigning=true ver."
            )
        }
        val missing = requiredKeys.filter { signingProps.getProperty(it).isNullOrBlank() }
        if (missing.isNotEmpty()) {
            throw GradleException("android/key.properties eksik alanlar: ${missing.joinToString()}")
        }
    }

    signingConfigs {
        if (requiredKeys.all { !signingProps.getProperty(it).isNullOrBlank() }) {
            create("release") {
                storeFile = file(signingProps.getProperty("storeFile"))
                storePassword = signingProps.getProperty("storePassword")
                keyAlias = signingProps.getProperty("keyAlias")
                keyPassword = signingProps.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        release {
            val cfg = signingConfigs.findByName("release")
            if (cfg != null) {
                signingConfig = cfg
            } else if (allowDebugSigning) {
                logger.warn("UYARI: release DEBUG anahtarıyla imzalanıyor; mağazaya yükleme.")
                signingConfig = signingConfigs.getByName("debug")
            }
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
