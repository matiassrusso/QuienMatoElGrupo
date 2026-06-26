import { useRef, type DragEvent } from "react"

interface Props {
  file: File | null
  onFileSelected: (file: File) => void
}

function FileUploader({ file, onFileSelected }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const dropped = e.dataTransfer.files[0]
    if (dropped) onFileSelected(dropped)
  }

  return (
    <div
      className="uploader"
      role="button"
      tabIndex={0}
      aria-label="Seleccionar archivo zip exportado de WhatsApp"
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault()
          inputRef.current?.click()
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".zip"
        hidden
        onChange={(e) => {
          const selected = e.target.files?.[0]
          if (selected) onFileSelected(selected)
        }}
      />

      <span className="uploader-badge">ZIP</span>

      {file ? (
        <>
          <p className="uploader-title">Archivo listo para analizar</p>
          <p className="uploader-filename">{file.name}</p>
        </>
      ) : (
        <>
          <p className="uploader-title">Arrastra el .zip exportado de WhatsApp</p>
          <p className="uploader-hint">O haz clic para elegirlo. El contenido no se guarda.</p>
        </>
      )}
    </div>
  )
}

export default FileUploader
