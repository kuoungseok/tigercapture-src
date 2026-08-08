#target photoshop

(function () {
    function quote(value) {
        return "\"" + String(value).replace(/\\/g, "\\\\").replace(/\"/g, "\\\"").replace(/\r/g, "\\r").replace(/\n/g, "\\n") + "\"";
    }
    function array(values) {
        var rows = [];
        for (var i = 0; i < values.length; i++) rows.push(quote(values[i]));
        return "[" + rows.join(",") + "]";
    }
    function readText(path) {
        var file = new File(path);
        file.encoding = "UTF8";
        if (!file.open("r")) throw new Error("Cannot read " + path);
        var text = file.read();
        file.close();
        return text;
    }
    function layerNames(document) {
        var names = [];
        for (var i = 0; i < document.layers.length; i++) names.push(document.layers[i].name);
        return names;
    }
    function colorProfileName(document) {
        try {
            return document.colorProfileName;
        } catch (error) {
            return "";
        }
    }
    function openAndRoundtrip(folder, name) {
        var source = new File(folder.fsName + "/" + name);
        var document = app.open(source);
        var result = {
            source_name: name,
            document_name: document.name,
            width_px: Math.round(document.width.as("px")),
            height_px: Math.round(document.height.as("px")),
            bits_per_channel: document.bitsPerChannel.toString(),
            mode: document.mode.toString(),
            color_profile_name: colorProfileName(document),
            channel_count: document.channels.length,
            layer_count: document.layers.length,
            layer_names: layerNames(document)
        };
        var stem = name.replace(/\.[^.]+$/, "");
        var roundtrip = new File(folder.fsName + "/photoshop_roundtrip_" + stem + ".psd");
        var options = new PhotoshopSaveOptions();
        options.layers = true;
        options.alphaChannels = true;
        options.embedColorProfile = true;
        document.saveAs(roundtrip, options, true, Extension.LOWERCASE);
        result.roundtrip_path = roundtrip.fsName;
        document.close(SaveOptions.DONOTSAVECHANGES);
        return result;
    }
    function observation(value) {
        return "{" +
            "\"source_name\":" + quote(value.source_name) + "," +
            "\"document_name\":" + quote(value.document_name) + "," +
            "\"width_px\":" + value.width_px + "," +
            "\"height_px\":" + value.height_px + "," +
            "\"bits_per_channel\":" + quote(value.bits_per_channel) + "," +
            "\"mode\":" + quote(value.mode) + "," +
            "\"color_profile_name\":" + quote(value.color_profile_name) + "," +
            "\"channel_count\":" + value.channel_count + "," +
            "\"layer_count\":" + value.layer_count + "," +
            "\"layer_names\":" + array(value.layer_names) + "," +
            "\"roundtrip_path\":" + quote(value.roundtrip_path) +
            "}";
    }

    var repository = File($.fileName).parent.parent;
    var folder = new Folder(repository.fsName + "/debugCapture/painter/external_interop");
    var nonce = readText(folder.fsName + "/run_nonce.txt").replace(/\s+$/, "");
    var names = ["tiger_png8.png", "tiger_png16.png", "tiger_tiff16.tiff", "tiger_layers.psd"];
    var results = [];
    var previousDialogs = app.displayDialogs;
    app.displayDialogs = DialogModes.NO;
    try {
        for (var i = 0; i < names.length; i++) results.push(openAndRoundtrip(folder, names[i]));
    } finally {
        try { app.displayDialogs = previousDialogs; } catch (ignored) {}
    }
    var serialized = [];
    for (var j = 0; j < results.length; j++) serialized.push(observation(results[j]));
    var payload = "{\n" +
        "  \"schema\": \"tigerstudio.painter.photoshop-interop-observation.v1\",\n" +
        "  \"producer\": \"Adobe Photoshop\",\n" +
        "  \"producer_version\": " + quote(app.version) + ",\n" +
        "  \"execution\": \"photoshop_javascript\",\n" +
        "  \"run_nonce\": " + quote(nonce) + ",\n" +
        "  \"observations\": [" + serialized.join(",") + "]\n" +
        "}";
    var output = new File(folder.fsName + "/photoshop_observation.json");
    output.encoding = "UTF8";
    output.open("w");
    output.write(payload);
    output.close();
}());
