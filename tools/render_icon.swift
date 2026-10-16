// Composes the app icon with AppKit: a macOS squircle (824px body, 100px margin on a 1024 canvas) in the
// given colour, with the mark centred on it at 600px.
//   swift tools/render_icon.swift brand/logo-mark.png out.png 1024 1c1c1c
import AppKit

let args = CommandLine.arguments
guard args.count == 5, let size = Int(args[3]), let mark = NSImage(contentsOfFile: args[1]),
      let hex = UInt32(args[4], radix: 16) else {
  FileHandle.standardError.write("uso: render_icon.swift mark.png out.png size rrggbb\n".data(using: .utf8)!)
  exit(1)
}
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8,
                           samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
rep.size = NSSize(width: size, height: size)
let k = CGFloat(size) / 1024
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
NSGraphicsContext.current!.imageInterpolation = .high
NSColor(srgbRed: CGFloat(hex >> 16 & 0xff) / 255, green: CGFloat(hex >> 8 & 0xff) / 255,
        blue: CGFloat(hex & 0xff) / 255, alpha: 1).setFill()
NSBezierPath(roundedRect: NSRect(x: 100 * k, y: 100 * k, width: 824 * k, height: 824 * k),
             xRadius: 185 * k, yRadius: 185 * k).fill()
mark.draw(in: NSRect(x: 212 * k, y: 212 * k, width: 600 * k, height: 600 * k))
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: args[2]))
