import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  ALPHABET,
  formatSerial,
  gs1CheckDigit,
  gtinIsValid,
  luhn32CheckChar,
  luhn32IsValid,
  normaliseRaw,
  normaliseSerial,
  parse,
} from "./codes";

const V = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../../../docs/plan/test-vectors/codes.json", import.meta.url)), "utf8"),
);

const GTIN = "08901001000124";
const SERIAL = "TPM9S346Q37";

describe("check characters (same vectors as the Python package)", () => {
  it("uses the Crockford alphabet", () => {
    expect(ALPHABET).toBe(V.crockford_alphabet);
  });
  it.each(V.gtin_valid as string[])("valid GTIN %s", (g) => {
    expect(gtinIsValid(g)).toBe(true);
    expect(gs1CheckDigit(g.slice(0, 13))).toBe(g[13]);
  });
  it.each(V.gtin_invalid as string[])("invalid GTIN %s", (g) => expect(gtinIsValid(g)).toBe(false));
  it.each(V.luhn32_check_examples as { payload: string; check: string }[])("check char for $payload", (c) =>
    expect(luhn32CheckChar(c.payload)).toBe(c.check),
  );
  it.each(V.serial_valid as string[])("valid serial %s", (s) => expect(luhn32IsValid(s)).toBe(true));
  it.each(V.serial_invalid as string[])("invalid serial %s", (s) => expect(luhn32IsValid(s)).toBe(false));
});

describe("normalising", () => {
  it.each(V.normalize_examples as { raw: string; serial: string }[])("serial from $raw", (c) => {
    expect(normaliseSerial(normaliseRaw(c.raw)).serial).toBe(c.serial);
  });
  it("strips the scanner symbology prefix and keeps GS", () => {
    expect(normaliseRaw("]Q3abc")).toBe("abc");
    expect(normaliseRaw("01\x1d21AB\r\n")).toBe("01\x1d21AB");
  });
  it("maps O, I, L to digits and reports U", () => {
    expect(normaliseSerial("tpl9-s346-qi7").serial).toBe("TP19S346Q17");
    expect(normaliseSerial("TPU9S346Q37").notes.some((n) => n.includes("U"))).toBe(true);
  });
});

interface FullCase {
  raw: string;
  gtin: string;
  serial: string;
  lot: string;
  expiry: string;
}

describe("parsing", () => {
  const expectFull = (raw: string, c: FullCase) => {
    const r = parse(raw);
    expect([r.gtin, r.serial, r.lot, r.expiry]).toEqual([c.gtin, c.serial, c.lot, c.expiry]);
    expect(r.status).toEqual({ gtin: "valid", serial: "valid", lot: "valid", expiry: "valid" });
    return r;
  };
  it.each(V.digital_link_examples as FullCase[])("digital link", (c) => {
    expect(expectFull(c.raw, c).grammar).toBe("digital_link");
  });
  it.each(V.element_string_examples as FullCase[])("element string", (c) => {
    expect(expectFull(c.raw, c).grammar).toBe("element_string");
  });
  it("element string without GS where the lot contains 21", () => {
    const r = parse(`01${GTIN}1727033110TP21A01721${SERIAL}`);
    expect([r.lot, r.serial]).toEqual(["TP21A017", SERIAL]);
  });
  it("label line in any order", () => {
    const r = parse(`LOT TP24A017 EXP 03/2027 SN TPM9-S346-Q37 GTIN ${GTIN}`);
    expect([r.grammar, r.gtin, r.serial, r.lot, r.expiry]).toEqual([
      "label_line",
      GTIN,
      SERIAL,
      "TP24A017",
      "2027-03-31",
    ]);
  });
  it("label variants", () => {
    const r = parse("B.No. K/24/0091  S/N KS6C-Q643-DZ3  Exp. MAR 2027");
    expect([r.lot, r.serial, r.expiry, r.status.gtin]).toEqual(["K/24/0091", "KS6CQ643DZ3", "2027-03-31", "missing"]);
  });
  it("bare serial, bad check char, bare GTIN, garbage", () => {
    expect(parse("tpm9-s346-q37").grammar).toBe("bare_serial");
    expect(parse("TPM0S346Q37").status.serial).toBe("invalid_check");
    expect(parse(GTIN).grammar).toBe("bare_gtin");
    expect(parse("hello world").grammar).toBe("unknown");
    expect(parse("").grammar).toBe("unknown");
  });
  it("expiry day 00 means the last day of the month", () => {
    expect(parse(`(01)${GTIN}(17)270200(10)X1(21)${SERIAL}`).expiry).toBe("2027-02-28");
  });
  it("formats serials in 4-4-3 groups", () => expect(formatSerial(SERIAL)).toBe("TPM9-S346-Q37"));
});
