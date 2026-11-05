// Aufruf: npm test (Node führt die TypeScript-Datei direkt aus)
import assert from "node:assert/strict";
import { test } from "node:test";
import { assess, hasProfileData, parseGrade, EMPTY_PROFILE } from "./admission.ts";

const labels = {
  fields: { informatik: "Informatik", wirtschaft: "Wirtschaft" },
  areas: { informatik: "Informatik", mathematik: "Mathematik" },
};

const master = {
  degree: "master",
  min_total_ects: 180,
  min_grade: 2.5,
  accepted_fields: ["informatik"],
  ects_requirements: [{ area: "informatik", ects: 60 }],
};

const profile = (over = {}) => ({
  field: "informatik",
  totalEcts: "180",
  grade: "2,0",
  areaEcts: { informatik: "70" },
  ...over,
});

const status = (result, key) => result.checks.find((c) => c.key === key).status;

test("alles erfüllt: passt voraussichtlich", () => {
  const r = assess(master, profile(), labels);
  assert.equal(r.fit, "likely");
  assert.ok(r.checks.every((c) => c.status === "met"));
});

test("Grenzwerte zählen als erfüllt", () => {
  const r = assess(master, profile({ grade: "2,5", areaEcts: { informatik: "60" } }), labels);
  assert.equal(r.fit, "likely");
});

test("Note knapp darüber ist teilweise, deutlich darüber nicht erfüllt", () => {
  assert.equal(status(assess(master, profile({ grade: "2,8" }), labels), "grade"), "partial");
  const far = assess(master, profile({ grade: "2,9" }), labels);
  assert.equal(status(far, "grade"), "unmet");
  assert.equal(far.fit, "unlikely");
});

test("fehlende ECTS: bis 30 nachholbar, darüber nicht erfüllt", () => {
  const near = assess({ ...master, min_total_ects: 210 }, profile(), labels);
  assert.equal(status(near, "total"), "partial");
  assert.equal(near.fit, "partial");
  assert.match(near.checks[0].detail, /30 ECTS/);
  const far = assess({ ...master, min_total_ects: 240 }, profile({ totalEcts: "180" }), labels);
  assert.equal(status(far, "total"), "unmet");
});

test("Fachgebiet: ab der Hälfte nachholbar", () => {
  assert.equal(status(assess(master, profile({ areaEcts: { informatik: "30" } }), labels), "area-informatik"), "partial");
  assert.equal(status(assess(master, profile({ areaEcts: { informatik: "29" } }), labels), "area-informatik"), "unmet");
});

test("anderes Bachelorfach ist nie ein hartes Nein", () => {
  const r = assess(master, profile({ field: "wirtschaft" }), labels);
  assert.equal(status(r, "field"), "partial");
  assert.equal(r.fit, "partial");
});

test("leeres Fachfeld heißt: kein bestimmtes Fach verlangt", () => {
  const r = assess({ ...master, accepted_fields: [] }, profile({ field: "wirtschaft" }), labels);
  assert.equal(r.checks.some((c) => c.key === "field"), false);
  assert.equal(r.fit, "likely");
});

test("fehlende Angaben: unvollständig, aber ein Nein bleibt ein Nein", () => {
  assert.equal(assess(master, EMPTY_PROFILE, labels).fit, "incomplete");
  assert.equal(assess(master, { ...EMPTY_PROFILE, grade: "3,5" }, labels).fit, "unlikely");
});

test("Bachelor wird nicht eingeschätzt", () => {
  const r = assess({ ...master, degree: "bachelor" }, profile(), labels);
  assert.deepEqual(r, { fit: "not_applicable", checks: [] });
});

test("Eingaben: Komma, ungültige Werte, leeres Profil", () => {
  assert.equal(parseGrade("2,3"), 2.3);
  assert.equal(parseGrade("0,5"), null);
  assert.equal(parseGrade("abc"), null);
  assert.equal(hasProfileData(EMPTY_PROFILE), false);
  assert.equal(hasProfileData({ ...EMPTY_PROFILE, grade: "abc" }), false);
  assert.equal(hasProfileData({ ...EMPTY_PROFILE, totalEcts: "0" }), true);
});

test("numeric aus der Datenbank kommt auch als Text richtig an", () => {
  const r = assess({ ...master, min_grade: "2.5" }, profile({ grade: "2,5" }), labels);
  assert.equal(status(r, "grade"), "met");
});
