ThisBuild / scalaVersion := "2.13.18"
ThisBuild / version := "0.1.0"
ThisBuild / organization := "local"

val chiselVersion = "7.6.0"

lazy val root = (project in file("."))
  .settings(
    name := "chext_template",
    Compile / unmanagedSourceDirectories += baseDirectory.value / "tests",
    libraryDependencies ++= Seq(
      "org.chipsalliance" %% "chisel" % chiselVersion,
      "hdlstuff" %% "hdlinfo" % "0.1.0",
      "hdlstuff" %% "chext" % "0.2.2"
    ),
    scalacOptions ++= Seq(
      "-language:reflectiveCalls",
      "-deprecation",
      "-feature",
      "-Xcheckinit",
      "-Ymacro-annotations"
    ),
    addCompilerPlugin(
      "org.chipsalliance" % "chisel-plugin" % chiselVersion cross CrossVersion.full
    )
  )
