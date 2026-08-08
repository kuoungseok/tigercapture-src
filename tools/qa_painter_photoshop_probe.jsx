#target photoshop

(function () {
    var repository = File($.fileName).parent.parent;
    var outputFolder = new Folder(repository.fsName + "/debugCapture/painter/external_interop");
    if (!outputFolder.exists) {
        outputFolder.create();
    }
    var output = new File(outputFolder.fsName + "/photoshop_probe.json");
    var payload = "{\n" +
        "  \"schema\": \"tigerstudio.painter.photoshop-probe.v1\",\n" +
        "  \"producer\": \"Adobe Photoshop\",\n" +
        "  \"producer_version\": \"" + app.version + "\",\n" +
        "  \"execution\": \"photoshop_javascript\",\n" +
        "  \"open_document_count\": " + app.documents.length + ",\n" +
        "  \"success\": true\n" +
        "}";
    output.encoding = "UTF8";
    output.open("w");
    output.write(payload);
    output.close();
}());
