class Brow < Formula
  include Language::Python::Virtualenv

  desc "Standalone Playwright CLI for agent browser automation"
  homepage "https://github.com/detrin/brow"
  url "https://files.pythonhosted.org/packages/source/b/brow-cli/brow_cli-0.1.3.tar.gz"
  sha256 "78279b18f48ee6560c3fbb08300bf76a8c95c177ebbc30bf38f098d66458f173"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
    system bin/"playwright", "install", "chromium"
  end

  def caveats
    <<~EOS
      Chromium is installed automatically during brew install.
      If you need to reinstall it:
        playwright install chromium
    EOS
  end

  test do
    assert_match "Usage", shell_output("#{bin}/brow --help")
  end
end
