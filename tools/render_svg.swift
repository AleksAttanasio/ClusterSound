// Renders an SVG to a square PNG with AppKit (NSImage reads SVG natively on macOS 14+).
//   swift tools/render_svg.swift brand/logo-app.svg out.png 1024
import AppKit

let args = CommandLine.arguments
guard args.count == 4, let size = Int(args[3]), let svg = NSImage(contentsOfFile: args[1]) else {
  FileHandle.standardError.write("uso: render_svg.swift in.svg out.png size\n".data(using: .utf8)!)
  exit(1)
}
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8,
                           samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                           colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
rep.size = NSSize(width: size, height: size)
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
svg.draw(in: NSRect(x: 0, y: 0, width: size, height: size))
NSGraphicsContext.restoreGraphicsState()
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: args[2]))
