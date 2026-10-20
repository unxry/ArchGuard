import AppKit

let folder = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
for size in [16, 32, 64, 128, 256, 512, 1024] {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    let transform = AffineTransform(scale: CGFloat(size) / 48)
    (transform as NSAffineTransform).concat()
    NSColor(calibratedRed: 27/255, green: 32/255, blue: 40/255, alpha: 1).setFill()
    NSBezierPath(roundedRect: NSRect(x: 2, y: 2, width: 44, height: 44), xRadius: 10, yRadius: 10).fill()
    let shape = NSBezierPath(); shape.windingRule = .evenOdd
    // Original product icon's four polygon contours; AppKit uses a flipped Y axis.
    for points: [(Double, Double)] in [
        [(20,2),(36,11),(36,29),(20,38),(4,29),(4,11)],
        [(20,8),(10,14),(10,26),(20,32),(30,26),(30,14)],
        [(20,12),(27,16),(27,24),(20,28),(13,24),(13,16)],
        [(20,17),(17,19),(17,22),(20,24),(23,22),(23,19)]
    ] {
        shape.move(to: NSPoint(x: points[0].0+4, y: 44-points[0].1))
        for p in points.dropFirst() { shape.line(to: NSPoint(x: p.0+4, y: 44-p.1)) }
        shape.close()
    }
    NSColor(calibratedRed: 231/255, green: 186/255, blue: 128/255, alpha: 1).setFill(); shape.fill()
    NSGraphicsContext.restoreGraphicsState()
    let data = bitmap.representation(using: .png, properties: [:])!
    if size <= 512 { try data.write(to: folder.appendingPathComponent("icon_\(size)x\(size).png")) }
    if size >= 32 { try data.write(to: folder.appendingPathComponent("icon_\(size/2)x\(size/2)@2x.png")) }
}
